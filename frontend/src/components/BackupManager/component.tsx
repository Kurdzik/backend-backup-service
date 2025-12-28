"use client"
import { post, get, del, put } from "@/lib/backendRequests"
import { useState, useEffect, useMemo } from "react"
import { Select, Stack, Modal, Button, Group, Table, Alert, Loader, ActionIcon, Badge, Center, Text, Paper, Tabs } from "@mantine/core"
import { IconTrash, IconPlus, IconRefresh, IconRestore, IconDatabase, IconServer, IconFolder, IconCloud } from "@tabler/icons-react"
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
    const [createModalOpened, setCreateModalOpened] = useState(false)
    const [restoreModalOpened, setRestoreModalOpened] = useState(false)
    const [deleteModalOpened, setDeleteModalOpened] = useState(false)
    const [selectedSourceId, setSelectedSourceId] = useState<string | null>(null)
    const [selectedDestinationId, setSelectedDestinationId] = useState<string | null>(null)
    const [selectedBackup, setSelectedBackup] = useState<Backup | null>(null)
    const [backupToDelete, setBackupToDelete] = useState<Backup | null>(null)
    const [loading, setLoading] = useState(false)
    const [notification, setNotification] = useState<NotificationState | null>(null)
    const [refreshKey, setRefreshKey] = useState(0)

    const [sources, setSources] = useState<BackupSource[]>([])
    const [destinations, setDestinations] = useState<BackupDestination[]>([])
    const [backups, setBackups] = useState<Backup[]>([])
    const [backupCount, setBackupCount] = useState(0)
    const [isLoading, setIsLoading] = useState(true)
    const [listDestinationId, setListDestinationId] = useState<string | null>(null)
    const [activeTab, setActiveTab] = useState<string | null>(null)

    useEffect(() => {
        const loadMetadata = async () => {
            setIsLoading(true)
            setNotification(null)
            try {
                const sourcesRes = await get("backup-sources/list")
                const sourcesList = sourcesRes.status < 400 ? (sourcesRes?.data?.backup_sources || []) : []
                setSources(sourcesList)

                const destinationsRes = await get("backup-destinations/list")
                const destinationsList = destinationsRes.status < 400 ? (destinationsRes?.data?.backup_destinations || []) : []
                setDestinations(destinationsList)

                if (destinationsList.length > 0 && !listDestinationId) {
                    setListDestinationId(String(destinationsList[0].id))
                }
            } catch (err) {
                setNotification({ message: "Failed to load sources and destinations", statusCode: 500 })
                console.error("Error loading metadata:", err)
            } finally {
                setIsLoading(false)
            }
        }

        loadMetadata()
    }, [])

    useEffect(() => {
        if (listDestinationId) {
            loadBackups()
        }
    }, [listDestinationId, refreshKey])

    const loadBackups = async () => {
        if (!listDestinationId) return

        setIsLoading(true)
        setNotification(null)
        try {
            const response = await get(`backup/list?backup_destination_id=${listDestinationId}`)
            
            if (response.status >= 400) {
                setNotification({ message: response.detail || "Failed to load backups", statusCode: response.status })
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
    }

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

    const getSourceName = (id: number) => sources.find(s => s.id === id)?.name || "Unknown"
    const getSourceById = (id: string) => sources.find(s => s.id === parseInt(id))

    const handleCreateBackup = async () => {
        if (!selectedSourceId || !selectedDestinationId) {
            setNotification({ message: "Please select both source and destination", statusCode: 400 })
            return
        }

        setLoading(true)
        setNotification(null)
        try {
            const response = await put(`backup/create?backup_source_id=${selectedSourceId}&backup_destination_id=${selectedDestinationId}`)

            if (response.status >= 400) {
                setNotification({ message: response.detail || "Failed to create backup", statusCode: response.status })
                return
            }

            setNotification({ message: response.message || "Backup is being created", statusCode: response.status })
            setCreateModalOpened(false)
            setSelectedSourceId(null)
            setSelectedDestinationId(null)
            
            setTimeout(() => {
                setRefreshKey(prev => prev + 1)
            }, 2000)
        } catch (err) {
            setNotification({ message: "Failed to create backup", statusCode: 500 })
            console.error(err)
        } finally {
            setLoading(false)
        }
    }

    const handleRestoreBackup = async () => {
        if (!selectedSourceId || !selectedDestinationId || !selectedBackup) {
            setNotification({ message: "Please select source, destination, and backup file", statusCode: 400 })
            return
        }

        setLoading(true)
        setNotification(null)
        try {
            const payload = {
                backup_source_id: parseInt(selectedSourceId),
                backup_destination_id: parseInt(selectedDestinationId),
                backup_path: selectedBackup.path
            }

            const response = await post("backup/restore", payload)

            if (response.status >= 400) {
                setNotification({ message: response.detail || "Failed to restore backup", statusCode: response.status })
                return
            }

            setNotification({ message: response.message || "Backup restored successfully", statusCode: response.status })
            setRestoreModalOpened(false)
            setSelectedSourceId(null)
            setSelectedDestinationId(null)
            setSelectedBackup(null)
        } catch (err) {
            setNotification({ message: "Failed to restore backup", statusCode: 500 })
            console.error(err)
        } finally {
            setLoading(false)
        }
    }

    const handleDeleteBackup = async () => {
        if (!listDestinationId || !backupToDelete) return

        setLoading(true)
        setNotification(null)
        try {
            const response = await del(`backup/delete?backup_destination_id=${listDestinationId}&backup_path=${encodeURIComponent(backupToDelete.path)}`)

            if (response.status >= 400) {
                setNotification({ message: response.detail || "Failed to delete backup", statusCode: response.status })
                return
            }

            setNotification({ message: response.message || "Backup deleted successfully", statusCode: response.status })
            setDeleteModalOpened(false)
            setBackupToDelete(null)
            setRefreshKey(prev => prev + 1)
        } catch (err) {
            setNotification({ message: "Failed to delete backup", statusCode: 500 })
            console.error(err)
        } finally {
            setLoading(false)
        }
    }

    const formatBytes = (bytes: number) => {
        if (bytes === 0) return '0 Bytes'
        const k = 1024
        const sizes = ['Bytes', 'KB', 'MB', 'GB']
        const i = Math.floor(Math.log(bytes) / Math.log(k))
        return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i]
    }

    const formatDate = (dateString: string) => {
        try {
            return new Date(dateString).toLocaleString()
        } catch {
            return dateString
        }
    }

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
                            <Table.Tr key={idx}>
                                <Table.Td style={{ fontFamily: "monospace", fontSize: 13 }}>{backup.name}</Table.Td>
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
                                            onClick={() => {
                                                setSelectedBackup(backup)
                                                // Ensure source_id is set as string for Select component
                                                setSelectedSourceId(String(backup.source_id))
                                                setSelectedDestinationId(listDestinationId)
                                                setRestoreModalOpened(true)
                                            }}
                                            title="Restore Backup"
                                        >
                                            <IconRestore size={16} />
                                        </ActionIcon>
                                        <ActionIcon
                                            color="red"
                                            variant="subtle"
                                            onClick={() => {
                                                setBackupToDelete(backup)
                                                setDeleteModalOpened(true)
                                            }}
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
                        onClick={() => setCreateModalOpened(true)}
                        disabled={isLoading}
                    >
                        Create Backup
                    </Button>
                    <ActionIcon 
                        onClick={() => setRefreshKey(prev => prev + 1)} 
                        loading={isLoading} 
                        variant="default"
                        size="lg"
                    >
                        <IconRefresh size={16} />
                    </ActionIcon>
                </Group>
            </Group>

            {notification && <DisplayNotification message={notification.message} statusCode={notification.statusCode} />}

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

            <Modal
                opened={createModalOpened}
                onClose={() => setCreateModalOpened(false)}
                title="Create New Backup"
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
                        <Button variant="default" onClick={() => setCreateModalOpened(false)}>
                            Cancel
                        </Button>
                    </Group>
                </Stack>
            </Modal>

            <Modal
                opened={restoreModalOpened}
                onClose={() => setRestoreModalOpened(false)}
                title="Restore Backup"
            >
                <Stack>
                    <Alert color="orange" title="Warning">
                        Restoring a backup will overwrite the current data in the selected source!
                    </Alert>

                    {selectedBackup && (
                        <Paper p="sm" withBorder>
                            <Text size="sm" fw={500} mb={4}>Selected Backup:</Text>
                            <Text size="sm" style={{ fontFamily: "monospace" }}>{selectedBackup.name}</Text>
                            <Text size="xs" c="dimmed">Size: {formatBytes(selectedBackup.size)}</Text>
                            <Text size="xs" c="dimmed">Modified: {formatDate(selectedBackup.modified)}</Text>
                        </Paper>
                    )}

                    <Select
                        label="Restore To (Source)"
                        placeholder="Select destination to restore to"
                        data={sourceOptions}
                        value={selectedSourceId}
                        onChange={setSelectedSourceId}
                        searchable
                        required
                        description={selectedBackup ? `Original source: ${getSourceById(selectedBackup.source_id)?.name || 'Unknown'}` : undefined}
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

                    <Group mt={20}>
                        <Button
                            onClick={handleRestoreBackup}
                            disabled={!selectedSourceId || !selectedDestinationId || !selectedBackup}
                            loading={loading}
                            color="orange"
                        >
                            Restore Backup
                        </Button>
                        <Button variant="default" onClick={() => setRestoreModalOpened(false)}>
                            Cancel
                        </Button>
                    </Group>
                </Stack>
            </Modal>

            <Modal
                opened={deleteModalOpened}
                onClose={() => setDeleteModalOpened(false)}
                title="Delete Backup"
            >
                <Stack>
                    <Alert color="red" title="Warning">
                        This action cannot be undone. The backup file will be permanently deleted.
                    </Alert>

                    {backupToDelete && (
                        <Paper p="sm" withBorder>
                            <Text size="sm" fw={500} mb={4}>Backup to Delete:</Text>
                            <Text size="sm" style={{ fontFamily: "monospace" }}>{backupToDelete.name}</Text>
                            <Text size="xs" c="dimmed">Size: {formatBytes(backupToDelete.size)}</Text>
                            <Text size="xs" c="dimmed">Modified: {formatDate(backupToDelete.modified)}</Text>
                            <Text size="xs" c="dimmed">Source: {getSourceById(backupToDelete.source_id)?.name || 'Unknown'}</Text>
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
                        <Button variant="default" onClick={() => setDeleteModalOpened(false)}>
                            Cancel
                        </Button>
                    </Group>
                </Stack>
            </Modal>
        </div>
    )
}