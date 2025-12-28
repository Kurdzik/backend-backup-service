"use client"
import { post, get, del } from "@/lib/backendRequests"
import { useState, useEffect, useMemo } from "react"
import { Select, Stack, Modal, TextInput, NumberInput, Button, Group, Table, Alert, Loader, ActionIcon, Badge, Checkbox, Center } from "@mantine/core"
import { IconEdit, IconTrash, IconPlus, IconRefresh } from "@tabler/icons-react"
import { DisplayNotification } from "../Notifications/component"

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

interface BackupSchedule {
    id: number
    name: string
    source_id: number
    destination_id: number
    schedule: string
    keep_n: number
    is_active: boolean
    last_run: string | null
    next_run: string | null
    created_at: string
    updated_at: string
}

interface NotificationState {
    message: string
    statusCode: number
}

export function BackupScheduleManager() {
    const [modalOpened, setModalOpened] = useState(false)
    const [scheduleName, setScheduleName] = useState<string>("")
    const [sourceId, setSourceId] = useState<string | null>(null)
    const [destinationId, setDestinationId] = useState<string | null>(null)
    const [cronExpression, setCronExpression] = useState<string>("*/5 * * * *")
    const [customCron, setCustomCron] = useState<string>("")
    const [isCustomCron, setIsCustomCron] = useState<boolean>(false)
    const [keepN, setKeepN] = useState<number>(3)
    const [isActive, setIsActive] = useState<boolean>(true)
    const [loading, setLoading] = useState(false)
    const [notification, setNotification] = useState<NotificationState | null>(null)
    const [editingId, setEditingId] = useState<number | null>(null)
    const [refreshKey, setRefreshKey] = useState(0)

    const [sources, setSources] = useState<BackupSource[]>([])
    const [destinations, setDestinations] = useState<BackupDestination[]>([])
    const [schedules, setSchedules] = useState<BackupSchedule[]>([])
    const [isLoading, setIsLoading] = useState(true)

    useEffect(() => {
        const loadData = async () => {
            setIsLoading(true)
            setNotification(null)
            try {
                // Fetch sources
                const sourcesRes = await get("backup-sources/list")
                const sourcesList = sourcesRes.status < 400 ? (sourcesRes?.data?.backup_sources || []) : []
                setSources(sourcesList)

                // Fetch destinations
                const destinationsRes = await get("backup-destinations/list")
                const destinationsList = destinationsRes.status < 400 ? (destinationsRes?.data?.backup_destinations || []) : []
                setDestinations(destinationsList)

                // Fetch schedules
                const schedulesRes = await get("backup-schedules/list")
                const schedulesList = schedulesRes.status < 400 ? (schedulesRes?.data?.backup_schedules || []) : []
                setSchedules(schedulesList)
            } catch (err) {
                setNotification({ message: "Failed to load data", statusCode: 500 })
                console.error("Error loading data:", err)
            } finally {
                setIsLoading(false)
            }
        }

        loadData()
    }, [refreshKey])

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

    const getSourceName = (id: number) => sources.find(s => s.id === id)?.name || "Unknown"
    const getDestinationName = (id: number) => destinations.find(d => d.id === id)?.name || "Unknown"

    const resetForm = () => {
        setScheduleName("")
        setSourceId(null)
        setDestinationId(null)
        setCronExpression("*/5 * * * *")
        setCustomCron("")
        setIsCustomCron(false)
        setKeepN(3)
        setIsActive(true)
    }

    const handleAddSchedule = async () => {
        if (!sourceId || !destinationId) {
            setNotification({ message: "Please fill in all required fields", statusCode: 400 })
            return
        }

        setLoading(true)
        setNotification(null)
        try {
            const payload = {
                schedule_name: scheduleName,
                backup_source_id: parseInt(sourceId),
                backup_destination_id: parseInt(destinationId),
                backup_schedule: isCustomCron ? customCron : cronExpression,
                keep_n: keepN
            }

            const response = await post("backup-schedules/add", payload)

            if (response.status >= 400) {
                setNotification({ message: response.detail || "Failed to add backup schedule", statusCode: response.status })
                return
            }

            setNotification({ message: response.message || "Backup schedule added successfully", statusCode: response.status })
            setModalOpened(false)
            resetForm()
            setRefreshKey(prev => prev + 1)
        } catch (err) {
            setNotification({ message: "Failed to add backup schedule", statusCode: 500 })
            console.error(err)
        } finally {
            setLoading(false)
        }
    }

    const handleUpdateSchedule = async (scheduleId: number) => {
        if (!sourceId || !destinationId) {
            setNotification({ message: "Please fill in all required fields", statusCode: 400 })
            return
        }

        setLoading(true)
        setNotification(null)
        try {
            const payload = {
                schedule_id: scheduleId,
                schedule_name: scheduleName,
                backup_source_id: parseInt(sourceId),
                backup_destination_id: parseInt(destinationId),
                backup_schedule: isCustomCron ? customCron : cronExpression,
                keep_n: keepN,
                is_active: isActive
            }

            const response = await post("backup-schedules/update", payload)

            if (response.status >= 400) {
                setNotification({ message: response.detail || "Failed to update backup schedule", statusCode: response.status })
                return
            }

            setNotification({ message: response.message || "Backup schedule updated successfully", statusCode: response.status })
            setModalOpened(false)
            setEditingId(null)
            resetForm()
            setRefreshKey(prev => prev + 1)
        } catch (err) {
            setNotification({ message: "Failed to update backup schedule", statusCode: 500 })
            console.error(err)
        } finally {
            setLoading(false)
        }
    }

    const handleDeleteSchedule = async (scheduleId: number) => {
        if (!window.confirm("Are you sure you want to delete this backup schedule?")) return

        setNotification(null)
        try {
            const response = await del(`backup-schedules/delete?schedule_id=${scheduleId}`)

            if (response.status >= 400) {
                setNotification({ message: response.detail || "Failed to delete backup schedule", statusCode: response.status })
                return
            }

            setNotification({ message: response.message || "Backup schedule deleted successfully", statusCode: response.status })
            setRefreshKey(prev => prev + 1)
        } catch (err) {
            setNotification({ message: "Failed to delete backup schedule", statusCode: 500 })
            console.error(err)
        }
    }

    const openEditModal = (schedule: BackupSchedule) => {
        setEditingId(schedule.id)
        setScheduleName(schedule.name)
        setSourceId(schedule.source_id.toString())
        setDestinationId(schedule.destination_id.toString())
        const commonCrons = ["*/5 * * * *", "0 * * * *", "0 0 * * *", "0 0 * * 0", "0 0 1 * *"]
        setIsCustomCron(!commonCrons.includes(schedule.schedule))
        setCronExpression(schedule.schedule)
        setCustomCron(schedule.schedule)
        setKeepN(schedule.keep_n)
        setIsActive(schedule.is_active)
        setModalOpened(true)
    }

    const isFormValid = sourceId && destinationId

    const ScheduleTable = ({ schedules }: { schedules: BackupSchedule[] }) => (
        <Table striped>
            <Table.Thead>
                <Table.Tr>
                    <Table.Th>Name</Table.Th>
                    <Table.Th>Source</Table.Th>
                    <Table.Th>Destination</Table.Th>
                    <Table.Th>Schedule</Table.Th>
                    <Table.Th>Retain</Table.Th>
                    <Table.Th>Status</Table.Th>
                    <Table.Th>Last Run</Table.Th>
                    <Table.Th>Actions</Table.Th>
                </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
                {schedules.length === 0 ? (
                    <Table.Tr>
                        <Table.Td colSpan={8} style={{ textAlign: "center", color: "#999" }}>
                            No schedules configured
                        </Table.Td>
                    </Table.Tr>
                ) : (
                    schedules.map((schedule) => (
                        <Table.Tr key={schedule.id}>
                            <Table.Td>{schedule.name}</Table.Td>
                            <Table.Td style={{ fontSize: 12 }}>{getSourceName(schedule.source_id)}</Table.Td>
                            <Table.Td style={{ fontSize: 12 }}>{getDestinationName(schedule.destination_id)}</Table.Td>
                            <Table.Td style={{ fontSize: 12, fontFamily: "monospace" }}>{schedule.schedule}</Table.Td>
                            <Table.Td>{schedule.keep_n} backups</Table.Td>
                            <Table.Td>
                                <Badge color={schedule.is_active ? "green" : "gray"}>
                                    {schedule.is_active ? "Active" : "Inactive"}
                                </Badge>
                            </Table.Td>
                            <Table.Td style={{ fontSize: 12 }}>
                                {schedule.last_run ? new Date(schedule.last_run).toLocaleString() : "Never"}
                            </Table.Td>
                            <Table.Td>
                                <Group gap={8}>
                                    <ActionIcon
                                        size="sm"
                                        variant="default"
                                        onClick={() => openEditModal(schedule)}
                                        title="Edit Schedule"
                                    >
                                        <IconEdit size={16} />
                                    </ActionIcon>
                                    <ActionIcon
                                        color="red"
                                        variant="subtle"
                                        onClick={() => handleDeleteSchedule(schedule.id)}
                                        title="Delete Schedule"
                                    >
                                        <IconTrash size={16} />
                                    </ActionIcon>
                                </Group>
                            </Table.Td>
                        </Table.Tr>
                    ))
                )}
            </Table.Tbody>
        </Table>
    )

    return (
        <div style={{ padding: 20 }}>
            <Group mb={20}>
                <h1>Backup Schedules</h1>
                <Button
                    leftSection={<IconPlus size={16} />}
                    onClick={() => {
                        setEditingId(null)
                        resetForm()
                        setModalOpened(true)
                    }}
                    disabled={isLoading}
                >
                    Add Schedule
                </Button>
                <ActionIcon onClick={() => setRefreshKey(prev => prev + 1)} loading={isLoading} variant="default">
                    <IconRefresh size={16} />
                </ActionIcon>
            </Group>

            {notification && <DisplayNotification message={notification.message} statusCode={notification.statusCode} />}

            {isLoading ? (
                <Center py={40}>
                    <Loader />
                </Center>
            ) : (
                <ScheduleTable schedules={schedules} />
            )}

            <Modal
                opened={modalOpened}
                onClose={() => setModalOpened(false)}
                title={editingId ? "Edit Backup Schedule" : "Add Backup Schedule"}
            >
                <Stack>
                    <TextInput
                        label="Schedule Name"
                        value={scheduleName}
                        onChange={(e) => setScheduleName(e.currentTarget.value)}
                        placeholder="e.g., Daily Production Backup"
                    />

                    <Select
                        label="Backup Source"
                        placeholder="Select a source"
                        data={sourceOptions}
                        value={sourceId}
                        onChange={setSourceId}
                        searchable
                        required
                    />

                    <Select
                        label="Backup Destination"
                        placeholder="Select a destination"
                        data={destinationOptions}
                        value={destinationId}
                        onChange={setDestinationId}
                        searchable
                        required
                    />

                    <Select
                        label="Cron Expression"
                        placeholder="Select a schedule"
                        data={[
                            { value: "*/5 * * * *", label: "Every 5 minutes" },
                            { value: "0 * * * *", label: "Every hour" },
                            { value: "0 0 * * *", label: "Daily at midnight" },
                            { value: "0 0 * * 0", label: "Weekly (Sundays at midnight)" },
                            { value: "0 0 1 * *", label: "Monthly (1st at midnight)" },
                            { value: "custom", label: "Custom Cron Expression" }
                        ]}
                        value={isCustomCron ? "custom" : cronExpression}
                        onChange={(value) => {
                            if (value === "custom") {
                                setIsCustomCron(true)
                            } else if (value) {
                                setIsCustomCron(false)
                                setCronExpression(value)
                            }
                        }}
                        searchable
                        required
                    />

                    {isCustomCron && (
                        <TextInput
                            label="Custom Cron Expression"
                            value={customCron}
                            onChange={(e) => {
                                setCustomCron(e.currentTarget.value)
                                setCronExpression(e.currentTarget.value)
                            }}
                            placeholder="*/5 * * * *"
                            description="Use standard cron syntax (e.g., */5 * * * * for every 5 minutes)"
                            required
                        />
                    )}

                    <NumberInput
                        label="Retain Backups"
                        value={keepN}
                        onChange={(value) => setKeepN(typeof value === 'number' ? value : 3)}
                        min={1}
                        description="Number of backups to keep"
                        required
                    />

                    <Checkbox
                        label="Active"
                        checked={isActive}
                        onChange={(e) => setIsActive(e.currentTarget.checked)}
                        description="Enable or disable this backup schedule"
                    />

                    <Group mt={20}>
                        <Button
                            onClick={() => editingId ? handleUpdateSchedule(editingId) : handleAddSchedule()}
                            disabled={!isFormValid}
                            loading={loading}
                        >
                            {editingId ? "Update" : "Add"} Schedule
                        </Button>
                        <Button variant="default" onClick={() => setModalOpened(false)}>
                            Cancel
                        </Button>
                    </Group>
                </Stack>
            </Modal>
        </div>
    )
}