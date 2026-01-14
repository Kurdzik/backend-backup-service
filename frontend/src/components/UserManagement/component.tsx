"use client"
import { post, get } from "@/lib/backendRequests"
import { useState, useEffect } from "react"
import { 
    Stack, 
    Modal, 
    Button, 
    Group, 
    Table, 
    Alert, 
    Loader, 
    Center, 
    Text, 
    Paper, 
    Tabs,
    TextInput,
    PasswordInput,
    Badge,
    Code,
    Select
} from "@mantine/core"
import { IconUser, IconList, IconKey, IconRefresh } from "@tabler/icons-react"
import { DisplayNotification } from "../Notifications/component"

interface UserInfo {
    tenant_id: string
    user_id: number
    username: string
}

interface Log {
    id: number
    log: string
    timestamp: string
    tenant_id: string
    service_name: string
}

interface NotificationState {
    message: string
    statusCode: number
}

// Separate LogsTable component
function LogsTable({ logs, isLoading }: { logs: Log[], isLoading: boolean }) {
    const [pageSize, setPageSize] = useState("20")
    
    const formatTimestamp = (timestamp: string) => {
        try {
            return new Date(timestamp).toLocaleString()
        } catch {
            return timestamp
        }
    }

    const parseLogJson = (logString: string) => {
        try {
            return JSON.parse(logString)
        } catch {
            return null
        }
    }

    // Sort logs from newest to oldest
    const sortedLogs = [...logs].sort((a, b) => {
        return new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
    })

    // Limit displayed logs based on pageSize
    const displayedLogs = sortedLogs.slice(0, parseInt(pageSize))

    if (isLoading) {
        return (
            <Center py={40}>
                <Loader />
            </Center>
        )
    }

    return (
        <Stack gap="md">
            <Group justify="space-between">
                <Text size="sm" c="dimmed">
                    Showing {displayedLogs.length} of {logs.length} logs
                </Text>
                <Select
                    value={pageSize}
                    onChange={(value) => setPageSize(value || "20")}
                    data={[
                        { value: "20", label: "Show 20" },
                        { value: "50", label: "Show 50" },
                        { value: "150", label: "Show 150" },
                        { value: "200", label: "Show 200" }
                    ]}
                    style={{ width: 120 }}
                />
            </Group>

            <Table striped highlightOnHover>
                <Table.Thead>
                    <Table.Tr>
                        <Table.Th>ID</Table.Th>
                        <Table.Th>Timestamp</Table.Th>
                        <Table.Th>Service</Table.Th>
                        <Table.Th>Event</Table.Th>
                        <Table.Th>Details</Table.Th>
                    </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                    {displayedLogs.length === 0 ? (
                        <Table.Tr>
                            <Table.Td colSpan={5} style={{ textAlign: "center", color: "#999" }}>
                                No logs found
                            </Table.Td>
                        </Table.Tr>
                    ) : (
                        displayedLogs.map((log) => {
                            const parsedLog = parseLogJson(log.log)
                            return (
                                <Table.Tr key={log.id}>
                                    <Table.Td>{log.id}</Table.Td>
                                    <Table.Td style={{ fontSize: 12 }}>
                                        {formatTimestamp(log.timestamp)}
                                    </Table.Td>
                                    <Table.Td>
                                        <Badge variant="light" size="sm">
                                            {log.service_name}
                                        </Badge>
                                    </Table.Td>
                                    <Table.Td style={{ fontSize: 13 }}>
                                        {parsedLog?.event || "N/A"}
                                    </Table.Td>
                                    <Table.Td>
                                        <Code 
                                            block 
                                            style={{ 
                                                fontSize: 11, 
                                                maxWidth: 400, 
                                                overflow: "auto",
                                                whiteSpace: "pre-wrap"
                                            }}
                                        >
                                            {JSON.stringify(parsedLog, null, 2)}
                                        </Code>
                                    </Table.Td>
                                </Table.Tr>
                            )
                        })
                    )}
                </Table.Tbody>
            </Table>
        </Stack>
    )
}

export function UserManagement() {
    const [activeTab, setActiveTab] = useState<string | null>("info")
    const [userInfo, setUserInfo] = useState<UserInfo | null>(null)
    const [logs, setLogs] = useState<Log[]>([])
    const [isLoading, setIsLoading] = useState(false)
    const [notification, setNotification] = useState<NotificationState | null>(null)
    const [passwordLoading, setPasswordLoading] = useState(false)
    
    // Password form state
    const [oldPassword, setOldPassword] = useState("")
    const [newPassword, setNewPassword] = useState("")
    const [newPassword2, setNewPassword2] = useState("")

    useEffect(() => {
        loadUserInfo()
    }, [])

    const loadUserInfo = async () => {
        setIsLoading(true)
        setNotification(null)
        try {
            const response = await get("users/get-info")
            
            if (response.status >= 400) {
                setNotification({ message: response.detail || "Failed to load user info", statusCode: response.status })
                return
            }

            const info = response?.data
            setUserInfo(info)
        } catch (err) {
            setNotification({ message: "Failed to load user information", statusCode: 500 })
            console.error("Error loading user info:", err)
        } finally {
            setIsLoading(false)
        }
    }

    const loadLogs = async () => {
        setIsLoading(true)
        setNotification(null)
        try {
            const response = await get("system/logs")
            
            if (response.status >= 400) {
                setNotification({ message: response.detail || "Failed to load logs", statusCode: response.status })
                setLogs([])
                return
            }

            const logsList = response?.data?.logs || []
            setLogs(logsList)
        } catch (err) {
            setNotification({ message: "Failed to load logs", statusCode: 500 })
            setLogs([])
            console.error("Error loading logs:", err)
        } finally {
            setIsLoading(false)
        }
    }

    const handleTabChange = (value: string | null) => {
        setActiveTab(value)
        if (value === "logs") {
            loadLogs()
        }
    }

    const handleChangePassword = async () => {
        if (!oldPassword || !newPassword || !newPassword2) {
            setNotification({ message: "All fields are required", statusCode: 400 })
            return
        }

        if (newPassword !== newPassword2) {
            setNotification({ message: "New passwords do not match", statusCode: 400 })
            return
        }

        setPasswordLoading(true)
        setNotification(null)
        try {
            const payload = {
                username: userInfo?.username,
                old_password: oldPassword,
                new_password: newPassword,
                new_password2: newPassword2
            }

            const response = await post("users/change-password", payload)

            if (response.status >= 400) {
                setNotification({ message: response.detail || "Failed to change password", statusCode: response.status })
                return
            }

            setNotification({ message: response.message || "Password changed successfully", statusCode: response.status })
            // Clear form
            setOldPassword("")
            setNewPassword("")
            setNewPassword2("")
        } catch (err) {
            setNotification({ message: "Failed to change password", statusCode: 500 })
            console.error(err)
        } finally {
            setPasswordLoading(false)
        }
    }

    return (
        <div style={{ padding: 20 }}>
            <Group mb={20} justify="space-between">
                <div>
                    <h1 style={{ margin: 0 }}>User Management</h1>
                    <Text size="sm" c="dimmed">Manage your account and view system logs</Text>
                </div>
            </Group>

            {notification && <DisplayNotification message={notification.message} statusCode={notification.statusCode} />}

            <Tabs value={activeTab} onChange={handleTabChange}>
                <Tabs.List>
                    <Tabs.Tab value="info" leftSection={<IconUser size={16} />}>
                        User Info
                    </Tabs.Tab>
                    <Tabs.Tab value="password" leftSection={<IconKey size={16} />}>
                        Change Password
                    </Tabs.Tab>
                    <Tabs.Tab value="logs" leftSection={<IconList size={16} />}>
                        System Logs
                    </Tabs.Tab>
                </Tabs.List>

                <Tabs.Panel value="info" pt="md">
                    {isLoading ? (
                        <Center py={40}>
                            <Loader />
                        </Center>
                    ) : userInfo ? (
                        <Stack gap="md">
                            <Paper p="md" withBorder>
                                <Stack gap="sm">
                                    <Group>
                                        <Text fw={600} size="sm" style={{ width: 120 }}>Username:</Text>
                                        <Code>{userInfo.username}</Code>
                                    </Group>
                                    <Group>
                                        <Text fw={600} size="sm" style={{ width: 120 }}>User ID:</Text>
                                        <Code>{userInfo.user_id}</Code>
                                    </Group>
                                    <Group>
                                        <Text fw={600} size="sm" style={{ width: 120 }}>Tenant ID:</Text>
                                        <Code style={{ wordBreak: "break-all" }}>{userInfo.tenant_id}</Code>
                                    </Group>
                                </Stack>
                            </Paper>

                            <Button 
                                leftSection={<IconRefresh size={16} />}
                                onClick={loadUserInfo}
                                variant="light"
                            >
                                Refresh Info
                            </Button>
                        </Stack>
                    ) : (
                        <Alert color="yellow">No user information available</Alert>
                    )}
                </Tabs.Panel>

                <Tabs.Panel value="password" pt="md">
                    <Paper p="md" withBorder>
                        <Stack gap="md">
                            <Alert color="blue" title="Change Password">
                                Enter your current password and choose a new password.
                            </Alert>

                            <PasswordInput
                                label="Current Password"
                                value={oldPassword}
                                onChange={(e) => setOldPassword(e.target.value)}
                                required
                                placeholder="Enter your current password"
                            />

                            <PasswordInput
                                label="New Password"
                                value={newPassword}
                                onChange={(e) => setNewPassword(e.target.value)}
                                required
                                placeholder="Enter your new password"
                            />

                            <PasswordInput
                                label="Confirm New Password"
                                value={newPassword2}
                                onChange={(e) => setNewPassword2(e.target.value)}
                                required
                                placeholder="Confirm your new password"
                            />

                            <Button
                                onClick={handleChangePassword}
                                loading={passwordLoading}
                                disabled={!oldPassword || !newPassword || !newPassword2}
                            >
                                Change Password
                            </Button>
                        </Stack>
                    </Paper>
                </Tabs.Panel>

                <Tabs.Panel value="logs" pt="md">
                    <Group mb="md">
                        <Button
                            leftSection={<IconRefresh size={16} />}
                            onClick={loadLogs}
                            loading={isLoading}
                            variant="light"
                        >
                            Refresh Logs
                        </Button>
                    </Group>

                    <LogsTable logs={logs} isLoading={isLoading} />
                </Tabs.Panel>
            </Tabs>
        </div>
    )
}