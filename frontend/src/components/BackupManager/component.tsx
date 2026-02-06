"use client"
import { post, get, del, put } from "@/lib/backendRequests"
import { useState, useEffect, useMemo, useCallback } from "react"
import {
    Select,
    Stack,
    Modal,
    Button,
    Group,
    Table,
    Alert,
    Loader,
    ActionIcon,
    Badge,
    Center,
    Text,
    Paper,
    Tabs
} from "@mantine/core"
import {
    IconTrash,
    IconPlus,
    IconRefresh,
    IconRestore,
    IconDatabase,
    IconServer,
    IconFolder,
    IconCloud
} from "@tabler/icons-react"
import { DisplayNotification } from "../Notifications/component"
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from "recharts"

interface BackupSource {
    id: number
    source_type: string
    name: string
    url: string
}

interface BackupDestination {
    id: number
    destination_type: string
    name: string
    url: string
}

interface Backup {
    name: string
    path: string
    source: string
    source_id: string
    size: number
    modified: string
}

interface NotificationState {
    message: string
    statusCode: number
}

const getSourceIcon = (sourceType: string) => {
    const type = sourceType.toLowerCase()
    if (type.includes('postgres') || type.includes('mysql') || type.includes('database')) {
        return <IconDatabase size={16} />
    }
    if (type.includes('server') || type.includes('ssh')) {
        return <IconServer size={16} />
    }
    if (type.includes('s3') || type.includes('cloud')) {
        return <IconCloud size={16} />
    }
    return <IconFolder size={16} />
}

const CHART_COLORS = [
    '#2563eb', // blue
    '#dc2626', // red
    '#16a34a', // green
    '#ea580c', // orange
    '#9333ea', // purple
    '#0891b2', // cyan
    '#ca8a04', // yellow
    '#be123c', // rose
]

interface BackupGraphProps {
    backups: Backup[]
    sources: BackupSource[]
}

function BackupGraph({ backups, sources }: BackupGraphProps) {
    const chartData = useMemo(() => {
        // Get date 30 days ago
        const thirtyDaysAgo = new Date()
        thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 30)

        // Extract dates from backup filenames and filter last 30 days
        const backupsByDate: Record<string, Record<string, number>> = {}

        backups.forEach(backup => {
            // Try to extract date from filename (format: YYYYMMDD)
            const dateMatch = backup.name.match(/(\d{4})(\d{2})(\d{2})/)
            if (dateMatch) {
                const [, year, month, day] = dateMatch
                const backupDate = new Date(parseInt(year), parseInt(month) - 1, parseInt(day))
                
                // Only include backups from last 30 days
                if (backupDate >= thirtyDaysAgo) {
                    const dateKey = `${year}-${month}-${day}`
                    
                    if (!backupsByDate[dateKey]) {
                        backupsByDate[dateKey] = {}
                    }
                    
                    const sourceName = sources.find(s => s.id === parseInt(backup.source_id))?.name || backup.source
                    backupsByDate[dateKey][sourceName] = (backupsByDate[dateKey][sourceName] || 0) + 1
                }
            }
        })

        // Convert to array format for recharts and fill missing dates
        const dates: string[] = []
        for (let i = 29; i >= 0; i--) {
            const date = new Date()
            date.setDate(date.getDate() - i)
            const dateKey = date.toISOString().split('T')[0]
            dates.push(dateKey)
        }

        return dates.map(dateKey => {
            const formattedDate = dateKey.replace(/-/g, '')
            const dataPoint: any = { 
                date: new Date(dateKey).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
                fullDate: dateKey
            }
            
            // Add counts for each source
            const dayData = backupsByDate[formattedDate] || {}
            Object.keys(dayData).forEach(sourceName => {
                dataPoint[sourceName] = dayData[sourceName]
            })
            
            return dataPoint
        })
    }, [backups, sources])

    const sourceNames = useMemo(() => {
        const names = new Set<string>()
        backups.forEach(backup => {
            const sourceName = sources.find(s => s.id === parseInt(backup.source_id))?.name || backup.source
            names.add(sourceName)
        })
        return Array.from(names).sort()
    }, [backups, sources])

    if (backups.length === 0) {
        return (
            <Paper p="xl" withBorder mb="md">
                <Center>
                    <Text c="dimmed">No backup data available to display</Text>
                </Center>
            </Paper>
        )
    }

    return (
        <Paper p="md" withBorder mb="md">
            <Text size="lg" fw={600} mb="md">Backup Activity (Last 30 Days)</Text>
            <ResponsiveContainer width="100%" height={300}>
                <LineChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis 
                        dataKey="date" 
                        tick={{ fontSize: 12 }}
                        angle={-45}
                        textAnchor="end"
                        height={60}
                    />
                    <YAxis 
                        tick={{ fontSize: 12 }}
                        allowDecimals={false}
                    />
                    <Tooltip 
                        contentStyle={{ backgroundColor: '#fff', border: '1px solid #ccc' }}
                        labelStyle={{ fontWeight: 'bold' }}
                    />
                    <Legend 
                        wrapperStyle={{ paddingTop: '20px' }}
                        iconType="line"
                    />
                    {sourceNames.map((sourceName, idx) => (
                        <Line
                            key={sourceName}
                            type="monotone"
                            dataKey={sourceName}
                            stroke={CHART_COLORS[idx % CHART_COLORS.length]}
                            strokeWidth={2}
                            dot={{ r: 3 }}
                            activeDot={{ r: 5 }}
                        />
                    ))}
                </LineChart>
            </ResponsiveContainer>
        </Paper>
    )
}

export function BackupFileManager() {
    // Modal states
    const [createModalOpened, setCreateModalOpened] = useState(false)
    const [restoreModalOpened, setRestoreModalOpened] = useState(false)
    const [deleteModalOpened, setDeleteModalOpened] = useState(false)
    
    // Form states
    const [selectedSourceId, setSelectedSourceId] = useState<string | null>(null)
    const [selectedDestinationId, setSelectedDestinationId] = useState<string | null>(null)
    const [selectedBackup, setSelectedBackup] = useState<Backup | null>(null)
    const [backupToDelete, setBackupToDelete] = useState<Backup | null>(null)
    const [restoreToSourceId, setRestoreToSourceId] = useState<string | null>(null)
    
    // Data states
    const [sources, setSources] = useState<BackupSource[]>([])
    const [destinations, setDestinations] = useState<BackupDestination[]>([])
    const [backups, setBackups] = useState<Backup[]>([])
    const [backupCount, setBackupCount] = useState(0)
    
    // UI states
    const [loading, setLoading] = useState(false)
    const [isLoading, setIsLoading] = useState(true)
    const [notification, setNotification] = useState<NotificationState | null>(null)
    const [listDestinationId, setListDestinationId] = useState<string | null>(null)
    const [activeTab, setActiveTab] = useState<string | null>(null)

    // Fetch metadata (sources and destinations)
    const fetchMetadata = useCallback(async () => {
        setIsLoading(true)
        setNotification(null)
        try {
            // Fetch sources
            const sourcesRes = await get("backup-sources/list")
            if (sourcesRes.status >= 400) {
                setNotification({
                    message: sourcesRes.detail || "Failed to fetch backup sources",
                    statusCode: sourcesRes.status
                })
                setSources([])
            } else {
                const sourcesList = sourcesRes?.data?.backup_sources || []
                setSources(sourcesList)
            }

            // Fetch destinations
            const destinationsRes = await get("backup-destinations/list")
            if (destinationsRes.status >= 400) {
                setNotification({
                    message: destinationsRes.detail || "Failed to fetch backup destinations",
                    statusCode: destinationsRes.status
                })
                setDestinations([])
            } else {
                const destinationsList = destinationsRes?.data?.backup_destinations || []
                setDestinations(destinationsList)

                // Auto-select first destination if none selected
                if (destinationsList.length > 0 && !listDestinationId) {
                    setListDestinationId(String(destinationsList[0].id))
                }
            }
        } catch (err) {
            setNotification({ message: "Failed to load sources and destinations", statusCode: 500 })
            console.error("Error loading metadata:", err)
        } finally {
            setIsLoading(false)
        }
    }, [listDestinationId])

    // Fetch backups for selected destination
    const fetchBackups = useCallback(async () => {
        if (!listDestinationId) return

        setIsLoading(true)
        setNotification(null)
        try {
            const response = await get(`backup/list?backup_destination_id=${listDestinationId}`)
            
            if (response.status >= 400) {
                setNotification({ 
                    message: response.detail || "Failed to load backups", 
                    statusCode: response.status 
                })
                setBackups([])
                setBackupCount(0)
                return
            }

            const backupsList = response?.data?.backups || []
            const count = response?.data?.count || 0
            setBackups(backupsList)
            setBackupCount(count)

            // Set first source type as active tab if not set
            if (backupsList.length > 0 && !activeTab) {
                setActiveTab(backupsList[0].source)
            }
        } catch (err) {
            setNotification({ message: "Failed to load backups", statusCode: 500 })
            setBackups([])
            setBackupCount(0)
            console.error("Error loading backups:", err)
        } finally {
            setIsLoading(false)
        }
    }, [listDestinationId, activeTab])

    // Initial load
    useEffect(() => {
        fetchMetadata()
    }, [fetchMetadata])

    // Load backups when destination changes
    useEffect(() => {
        if (listDestinationId) {
            fetchBackups()
        }
    }, [listDestinationId, fetchBackups])

    // Memoized dropdown options
    const sourceOptions = useMemo(() => {
        return sources.map(s => ({
            value: String(s.id),
            label: `${s.name} (${s.source_type})`
        }))
    }, [sources])

    const destinationOptions = useMemo(() => {
        return destinations.map(d => ({
            value: String(d.id),
            label: `${d.name} (${d.destination_type})`
        }))
    }, [destinations])

    // Group backups by source type
    const backupsBySource = useMemo(() => {
        const grouped: Record<string, Backup[]> = {}
        backups.forEach(backup => {
            if (!grouped[backup.source]) {
                grouped[backup.source] = []
            }
            grouped[backup.source].push(backup)
        })
        return grouped
    }, [backups])

    const sourceTypes = useMemo(() => {
        return Object.keys(backupsBySource).sort()
    }, [backupsBySource])

    // Helper functions
    const getSourceName = useCallback((id: number) => {
        return sources.find(s => s.id === id)?.name || "Unknown"
    }, [sources])

    const getSourceById = useCallback((id: string) => {
        return sources.find(s => s.id === parseInt(id))
    }, [sources])

    const getSourcesByType = useCallback((sourceType: string) => {
        return sources.filter(s => s.source_type === sourceType)
    }, [sources])

    const formatBytes = useCallback((bytes: number) => {
        if (bytes === 0) return '0 Bytes'
        const k = 1024
        const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB']
        const i = Math.floor(Math.log(bytes) / Math.log(k))
        return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i]
    }, [])

    const formatDate = useCallback((dateString: string) => {
        try {
            return new Date(dateString).toLocaleString()
        } catch {
            return dateString
        }
    }, [])

    // Reset create form
    const resetCreateForm = useCallback(() => {
        setSelectedSourceId(null)
        setSelectedDestinationId(null)
    }, [])

    // Reset restore form
    const resetRestoreForm = useCallback(() => {
        setSelectedBackup(null)
        setRestoreToSourceId(null)
        setSelectedDestinationId(null)
    }, [])

    // Handle create backup
    const handleCreateBackup = async () => {
        if (!selectedSourceId || !selectedDestinationId) {
            setNotification({ 
                message: "Please select both source and destination", 
                statusCode: 400 
            })
            return
        }

        setLoading(true)
        setNotification(null)
        try {
            const response = await put(
                `backup/create?backup_source_id=${selectedSourceId}&backup_destination_id=${selectedDestinationId}`
            )

            if (response.status >= 400) {
                setNotification({ 
                    message: response.detail || "Failed to create backup", 
                    statusCode: response.status 
                })
                return
            }

            setNotification({ 
                message: response.message || "Backup is being created", 
                statusCode: response.status 
            })
            
            setCreateModalOpened(false)
            resetCreateForm()
            
            // Refresh backups after a delay
            setTimeout(() => {
                fetchBackups()
            }, 2000)
        } catch (err) {
            setNotification({ message: "Failed to create backup", statusCode: 500 })
            console.error(err)
        } finally {
            setLoading(false)
        }
    }

    // Handle restore backup
    const handleRestoreBackup = async () => {
        if (!restoreToSourceId || !selectedDestinationId || !selectedBackup) {
            setNotification({ 
                message: "Please select target source, destination, and backup file", 
                statusCode: 400 
            })
            return
        }

        setLoading(true)
        setNotification(null)
        try {
            const payload = {
                backup_source_id: parseInt(restoreToSourceId),
                backup_destination_id: parseInt(selectedDestinationId),
                backup_path: selectedBackup.path
            }

            console.log("Restoring backup with payload:", JSON.stringify(payload, null, 2))

            const response = await post("backup/restore", payload)

            if (response.status >= 400) {
                setNotification({ 
                    message: response.detail || "Failed to restore backup", 
                    statusCode: response.status 
                })
                return
            }

            setNotification({ 
                message: response.message || "Backup restored successfully", 
                statusCode: response.status 
            })
            
            setRestoreModalOpened(false)
            resetRestoreForm()
        } catch (err) {
            setNotification({ message: "Failed to restore backup", statusCode: 500 })
            console.error(err)
        } finally {
            setLoading(false)
        }
    }

    // Handle delete backup
    const handleDeleteBackup = async () => {
        if (!listDestinationId || !backupToDelete) {
            setNotification({ 
                message: "Missing destination or backup information", 
                statusCode: 400 
            })
            return
        }

        setLoading(true)
        setNotification(null)
        try {
            const response = await del(
                `backup/delete?backup_destination_id=${listDestinationId}&backup_path=${encodeURIComponent(backupToDelete.path)}`
            )

            if (response.status >= 400) {
                setNotification({ 
                    message: response.detail || "Failed to delete backup", 
                    statusCode: response.status 
                })
                return
            }

            setNotification({ 
                message: response.message || "Backup deleted successfully", 
                statusCode: response.status 
            })
            
            setDeleteModalOpened(false)
            setBackupToDelete(null)
            
            await fetchBackups()
        } catch (err) {
            setNotification({ message: "Failed to delete backup", statusCode: 500 })
            console.error(err)
        } finally {
            setLoading(false)
        }
    }

    // Open restore modal with backup pre-selected
    const openRestoreModal = useCallback((backup: Backup) => {
        setSelectedBackup(backup)
        setSelectedDestinationId(listDestinationId)
        
        // Find the original source
        const originalSource = getSourceById(backup.source_id)
        
        // Auto-select the original source if found
        if (originalSource) {
            setRestoreToSourceId(String(originalSource.id))
        } else {
            setRestoreToSourceId(null)
        }
        
        setRestoreModalOpened(true)
    }, [listDestinationId, getSourceById])

    // Open delete modal
    const openDeleteModal = useCallback((backup: Backup) => {
        setBackupToDelete(backup)
        setDeleteModalOpened(true)
    }, [])

    // Get compatible sources for restore (same type as backup)
    const getCompatibleSources = useCallback((backup: Backup | null) => {
        if (!backup) return sourceOptions

        const originalSource = getSourceById(backup.source_id)
        if (!originalSource) return sourceOptions

        // Filter sources by the same type
        const compatibleSources = sources.filter(s => s.source_type === originalSource.source_type)
        
        return compatibleSources.map(s => ({
            value: String(s.id),
            label: `${s.name} (${s.source_type})${s.id === originalSource.id ? ' - Original' : ''}`
        }))
    }, [sources, sourceOptions, getSourceById])

    const BackupTable = ({ backups }: { backups: Backup[] }) => (
        <Table striped highlightOnHover>
            <Table.Thead>
                <Table.Tr>
                    <Table.Th>Name</Table.Th>
                    <Table.Th>Size</Table.Th>
                    <Table.Th>Modified</Table.Th>
                    <Table.Th>Source</Table.Th>
                    <Table.Th>Actions</Table.Th>
                </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
                {backups.length === 0 ? (
                    <Table.Tr>
                        <Table.Td colSpan={5} style={{ textAlign: "center", color: "#999" }}>
                            No backups found for this source type
                        </Table.Td>
                    </Table.Tr>
                ) : (
                    backups.map((backup, idx) => {
                        const source = getSourceById(backup.source_id)
                        return (
                            <Table.Tr key={`${backup.path}-${idx}`}>
                                <Table.Td style={{ fontFamily: "monospace", fontSize: 13 }}>
                                    {backup.name}
                                </Table.Td>
                                <Table.Td>{formatBytes(backup.size)}</Table.Td>
                                <Table.Td style={{ fontSize: 12 }}>{formatDate(backup.modified)}</Table.Td>
                                <Table.Td>
                                    <Badge variant="light" size="sm">
                                        {source?.name || `ID: ${backup.source_id}`}
                                    </Badge>
                                </Table.Td>
                                <Table.Td>
                                    <Group gap={8}>
                                        <ActionIcon
                                            color="blue"
                                            variant="subtle"
                                            onClick={() => openRestoreModal(backup)}
                                            title="Restore Backup"
                                        >
                                            <IconRestore size={16} />
                                        </ActionIcon>
                                        <ActionIcon
                                            color="red"
                                            variant="subtle"
                                            onClick={() => openDeleteModal(backup)}
                                            title="Delete Backup"
                                        >
                                            <IconTrash size={16} />
                                        </ActionIcon>
                                    </Group>
                                </Table.Td>
                            </Table.Tr>
                        )
                    })
                )}
            </Table.Tbody>
        </Table>
    )

    return (
        <div style={{ padding: 20 }}>
            <Group mb={20} justify="space-between">
                <div>
                    <h1 style={{ margin: 0 }}>Backup Files</h1>
                    <Text size="sm" c="dimmed">Total: {backupCount} backups</Text>
                </div>
                <Group>
                    <Button
                        leftSection={<IconPlus size={16} />}
                        onClick={() => {
                            resetCreateForm()
                            setCreateModalOpened(true)
                        }}
                        disabled={isLoading}
                    >
                        Create Backup
                    </Button>
                    <ActionIcon 
                        onClick={fetchBackups} 
                        loading={isLoading} 
                        variant="default"
                        size="lg"
                    >
                        <IconRefresh size={16} />
                    </ActionIcon>
                </Group>
            </Group>

            {notification && (
                <DisplayNotification 
                    message={notification.message} 
                    statusCode={notification.statusCode} 
                />
            )}

            <Paper p="md" mb="md" withBorder>
                <Select
                    label="Select Destination to Browse Backups"
                    placeholder="Choose a backup destination"
                    data={destinationOptions}
                    value={listDestinationId}
                    onChange={(value) => {
                        setListDestinationId(value)
                        setActiveTab(null)
                    }}
                    searchable
                />
            </Paper>

            {isLoading ? (
                <Center py={40}>
                    <Loader />
                </Center>
            ) : (
                <>
                    <BackupGraph backups={backups} sources={sources} />
                    
                    {sourceTypes.length === 0 ? (
                        <Center py={40}>
                            <Text c="dimmed">No backups found for this destination</Text>
                        </Center>
                    ) : (
                        <Tabs value={activeTab} onChange={setActiveTab}>
                            <Tabs.List>
                                {sourceTypes.map(sourceType => (
                                    <Tabs.Tab 
                                        key={sourceType} 
                                        value={sourceType}
                                        leftSection={getSourceIcon(sourceType)}
                                    >
                                        {sourceType} ({backupsBySource[sourceType].length})
                                    </Tabs.Tab>
                                ))}
                            </Tabs.List>

                            {sourceTypes.map(sourceType => (
                                <Tabs.Panel key={sourceType} value={sourceType} pt="md">
                                    <BackupTable backups={backupsBySource[sourceType]} />
                                </Tabs.Panel>
                            ))}
                        </Tabs>
                    )}
                </>
            )}

            {/* Create Backup Modal */}
            <Modal
                opened={createModalOpened}
                onClose={() => {
                    setCreateModalOpened(false)
                    resetCreateForm()
                }}
                title="Create New Backup"
                size="lg"
            >
                <Stack>
                    <Select
                        label="Backup Source"
                        placeholder="Select a source to backup"
                        data={sourceOptions}
                        value={selectedSourceId}
                        onChange={setSelectedSourceId}
                        searchable
                        required
                    />

                    <Select
                        label="Backup Destination"
                        placeholder="Select where to store the backup"
                        data={destinationOptions}
                        value={selectedDestinationId}
                        onChange={setSelectedDestinationId}
                        searchable
                        required
                    />

                    <Alert color="blue" title="Note">
                        This will create a new backup of the selected source and store it in the selected destination.
                    </Alert>

                    <Group mt={20}>
                        <Button
                            onClick={handleCreateBackup}
                            disabled={!selectedSourceId || !selectedDestinationId}
                            loading={loading}
                        >
                            Create Backup
                        </Button>
                        <Button 
                            variant="default" 
                            onClick={() => {
                                setCreateModalOpened(false)
                                resetCreateForm()
                            }}
                        >
                            Cancel
                        </Button>
                    </Group>
                </Stack>
            </Modal>

            {/* Restore Backup Modal */}
            <Modal
                opened={restoreModalOpened}
                onClose={() => {
                    setRestoreModalOpened(false)
                    resetRestoreForm()
                }}
                title="Restore Backup"
                size="lg"
            >
                <Stack>
                    <Alert color="orange" title="Warning">
                        Restoring a backup will overwrite the current data in the selected source!
                    </Alert>

                    {selectedBackup && (
                        <Paper p="sm" withBorder>
                            <Text size="sm" fw={500} mb={4}>Selected Backup:</Text>
                            <Text size="sm" style={{ fontFamily: "monospace" }}>
                                {selectedBackup.name}
                            </Text>
                            <Text size="xs" c="dimmed">Size: {formatBytes(selectedBackup.size)}</Text>
                            <Text size="xs" c="dimmed">
                                Modified: {formatDate(selectedBackup.modified)}
                            </Text>
                            <Text size="xs" c="dimmed">
                                Original Source: {getSourceById(selectedBackup.source_id)?.name || 'Unknown'}
                            </Text>
                        </Paper>
                    )}

                    <Select
                        label="Restore To (Target Source)"
                        placeholder="Select source to restore to"
                        data={getCompatibleSources(selectedBackup)}
                        value={restoreToSourceId}
                        onChange={setRestoreToSourceId}
                        searchable
                        required
                        description={
                            selectedBackup 
                                ? `Compatible sources of type: ${getSourceById(selectedBackup.source_id)?.source_type || 'Unknown'}`
                                : "Select a backup first"
                        }
                    />

                    <Select
                        label="From Destination"
                        placeholder="Select backup location"
                        data={destinationOptions}
                        value={selectedDestinationId}
                        onChange={setSelectedDestinationId}
                        searchable
                        required
                    />

                    <Alert color="blue" title="Cross-Source Restore">
                        You can restore this backup to any source of the same type. For example, restore a 
                        PostgreSQL DB1 backup to PostgreSQL DB2.
                    </Alert>

                    <Group mt={20}>
                        <Button
                            onClick={handleRestoreBackup}
                            disabled={!restoreToSourceId || !selectedDestinationId || !selectedBackup}
                            loading={loading}
                            color="orange"
                        >
                            Restore Backup
                        </Button>
                        <Button 
                            variant="default" 
                            onClick={() => {
                                setRestoreModalOpened(false)
                                resetRestoreForm()
                            }}
                        >
                            Cancel
                        </Button>
                    </Group>
                </Stack>
            </Modal>

            {/* Delete Backup Modal */}
            <Modal
                opened={deleteModalOpened}
                onClose={() => {
                    setDeleteModalOpened(false)
                    setBackupToDelete(null)
                }}
                title="Delete Backup"
            >
                <Stack>
                    <Alert color="red" title="Warning">
                        This action cannot be undone. The backup file will be permanently deleted.
                    </Alert>

                    {backupToDelete && (
                        <Paper p="sm" withBorder>
                            <Text size="sm" fw={500} mb={4}>Backup to Delete:</Text>
                            <Text size="sm" style={{ fontFamily: "monospace" }}>
                                {backupToDelete.name}
                            </Text>
                            <Text size="xs" c="dimmed">Size: {formatBytes(backupToDelete.size)}</Text>
                            <Text size="xs" c="dimmed">
                                Modified: {formatDate(backupToDelete.modified)}
                            </Text>
                            <Text size="xs" c="dimmed">
                                Source: {getSourceById(backupToDelete.source_id)?.name || 'Unknown'}
                            </Text>
                        </Paper>
                    )}

                    <Group mt={20}>
                        <Button
                            onClick={handleDeleteBackup}
                            disabled={!backupToDelete}
                            loading={loading}
                            color="red"
                        >
                            Delete Backup
                        </Button>
                        <Button 
                            variant="default" 
                            onClick={() => {
                                setDeleteModalOpened(false)
                                setBackupToDelete(null)
                            }}
                        >
                            Cancel
                        </Button>
                    </Group>
                </Stack>
            </Modal>
        </div>
    )
}