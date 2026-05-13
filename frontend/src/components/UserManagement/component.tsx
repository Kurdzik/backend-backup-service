"use client"
import { post, get } from "@/lib/backendRequests"
import { useState, useEffect } from "react"
import { 
    Stack, 
    Button, 
    Group, 
    Table, 
    Alert, 
    Loader, 
    Center, 
    Text, 
    Paper, 
    Tabs,
    PasswordInput,
    Badge,
    Code,
    Select,
    NumberInput,
    TextInput,
    Switch,
    Divider
} from "@mantine/core"
import { useMantineColorScheme } from "@mantine/core"
import { IconUser, IconList, IconKey, IconRefresh, IconSun, IconMoon } from "@tabler/icons-react"
import { DisplayNotification } from "../Notifications/component"

interface UserInfo {
    tenant_id: string
    user_id: number
    username: string
    settings: UserSettings
}

interface UserSettings {
    log_retention_period_d: number
    log_size: number
    compression_enabled: boolean
    encryption_enabled: boolean
    encryption_key_configured: boolean
    key_fingerprint?: string | null
    gotify_enabled: boolean
    gotify_url?: string | null
    gotify_token_configured: boolean
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

    const getLevelColor = (level?: string) => {
        if (level === "critical" || level === "error") return "red"
        if (level === "warning") return "yellow"
        return "gray"
    }

    const getLogSummary = (parsedLog: any, rawLog: string) => {
        if (!parsedLog) return rawLog
        if (parsedLog.stage) return parsedLog.stage
        return parsedLog.error || parsedLog.detail || parsedLog.message || parsedLog.event || "No details"
    }

    const getTraceId = (parsedLog: any) => {
        return parsedLog?.task_id || parsedLog?.request_id
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
                        <Table.Th>Level</Table.Th>
                        <Table.Th>Timestamp</Table.Th>
                        <Table.Th>Service</Table.Th>
                        <Table.Th>Event</Table.Th>
                        <Table.Th>Summary</Table.Th>
                        <Table.Th>Trace</Table.Th>
                    </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                    {displayedLogs.length === 0 ? (
                        <Table.Tr>
                            <Table.Td colSpan={6}>
                                <div style={{ textAlign: "center", padding: "32px 0", color: "var(--lnr-text-faint)", fontSize: 13 }}>
                                    No logs found
                                </div>
                            </Table.Td>
                        </Table.Tr>
                    ) : (
                        displayedLogs.map((log) => {
                            const parsedLog = parseLogJson(log.log)
                            const traceId = getTraceId(parsedLog)
                            return (
                                <Table.Tr key={log.id}>
                                    <Table.Td>
                                        <Badge color={getLevelColor(parsedLog?.level)} variant="light" size="sm">
                                            {parsedLog?.level || "unknown"}
                                        </Badge>
                                    </Table.Td>
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
                                        <Text size="sm" lineClamp={3}>
                                            {getLogSummary(parsedLog, log.log)}
                                        </Text>
                                    </Table.Td>
                                    <Table.Td>
                                        {traceId ? (
                                            <Code>{traceId}</Code>
                                        ) : (
                                            <Text size="sm" c="dimmed">-</Text>
                                        )}
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
    const [settingsLoading, setSettingsLoading] = useState(false)
    const [keyLoading, setKeyLoading] = useState(false)
    const [logRetentionDays, setLogRetentionDays] = useState<number | string>(30)
    const [logSize, setLogSize] = useState<number | string>(1000000)
    const [compressionEnabled, setCompressionEnabled] = useState(false)
    const [encryptionEnabled, setEncryptionEnabled] = useState(false)
    const [encryptionKeyConfigured, setEncryptionKeyConfigured] = useState(false)
    const [keyFingerprint, setKeyFingerprint] = useState<string | null>(null)
    const [gotifyEnabled, setGotifyEnabled] = useState(false)
    const [gotifyUrl, setGotifyUrl] = useState("")
    const [gotifyToken, setGotifyToken] = useState("")
    const [gotifyTokenConfigured, setGotifyTokenConfigured] = useState(false)
    
    // Password form state
    const [oldPassword, setOldPassword] = useState("")
    const [newPassword, setNewPassword] = useState("")
    const [newPassword2, setNewPassword2] = useState("")
    const { colorScheme, toggleColorScheme } = useMantineColorScheme()

    useEffect(() => {
        loadUserInfo()
    }, [])

    const applySettings = (settings?: UserSettings) => {
        if (!settings) return
        setLogRetentionDays(settings.log_retention_period_d)
        setLogSize(settings.log_size)
        setCompressionEnabled(settings.compression_enabled)
        setEncryptionEnabled(settings.encryption_enabled)
        setEncryptionKeyConfigured(settings.encryption_key_configured)
        setKeyFingerprint(settings.key_fingerprint || null)
        setGotifyEnabled(settings.gotify_enabled)
        setGotifyUrl(settings.gotify_url || "")
        setGotifyTokenConfigured(settings.gotify_token_configured)
        setGotifyToken("")
    }

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
            applySettings(info?.settings)
        } catch (err) {
            setNotification({ message: "Failed to load user information", statusCode: 500 })
            console.error("Error loading user info:", err)
        } finally {
            setIsLoading(false)
        }
    }

    const loadLogs = async (showLoader = true) => {
        if (showLoader) setIsLoading(true)
        if (showLoader) setNotification(null)
        try {
            const response = await get("system/logs?min_level=info&limit=100")
            
            if (response.status >= 400) {
                setNotification({ message: response.detail || "Failed to load logs", statusCode: response.status })
                setLogs([])
                return
            }

            const logsList = response?.data?.logs || []
            setLogs(logsList)
        } catch (err) {
            if (showLoader) setNotification({ message: "Failed to load logs", statusCode: 500 })
            setLogs([])
            console.error("Error loading logs:", err)
        } finally {
            if (showLoader) setIsLoading(false)
        }
    }

    useEffect(() => {
        if (activeTab !== "logs") return

        const intervalId = window.setInterval(() => {
            loadLogs(false)
        }, 3000)

        return () => window.clearInterval(intervalId)
    }, [activeTab])

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

    const arrayBufferToPem = (buffer: ArrayBuffer, label: string) => {
        const bytes = new Uint8Array(buffer)
        let binary = ""
        bytes.forEach((byte) => {
            binary += String.fromCharCode(byte)
        })
        const base64 = window.btoa(binary)
        const body = base64.match(/.{1,64}/g)?.join("\n") || base64
        return `-----BEGIN ${label}-----\n${body}\n-----END ${label}-----`
    }

    const downloadPrivateKey = (privateKeyPem: string) => {
        const blob = new Blob([privateKeyPem], { type: "application/x-pem-file" })
        const url = URL.createObjectURL(blob)
        const link = document.createElement("a")
        link.href = url
        link.download = `backup-private-key-${userInfo?.tenant_id || "tenant"}.pem`
        document.body.appendChild(link)
        link.click()
        document.body.removeChild(link)
        URL.revokeObjectURL(url)
    }

    const handleGenerateEncryptionKey = async () => {
        setKeyLoading(true)
        setNotification(null)
        try {
            const keyPair = await window.crypto.subtle.generateKey(
                {
                    name: "RSA-OAEP",
                    modulusLength: 4096,
                    publicExponent: new Uint8Array([1, 0, 1]),
                    hash: "SHA-256",
                },
                true,
                ["encrypt", "decrypt"]
            )
            const publicKey = await window.crypto.subtle.exportKey("spki", keyPair.publicKey)
            const privateKey = await window.crypto.subtle.exportKey("pkcs8", keyPair.privateKey)
            const publicKeyPem = arrayBufferToPem(publicKey, "PUBLIC KEY")
            const privateKeyPem = arrayBufferToPem(privateKey, "PRIVATE KEY")

            const response = await post("users/encryption-key", { public_key: publicKeyPem })
            if (response.status >= 400) {
                setNotification({ message: response.detail || "Failed to save public key", statusCode: response.status })
                return
            }

            downloadPrivateKey(privateKeyPem)
            setEncryptionKeyConfigured(true)
            setKeyFingerprint(response?.data?.key_fingerprint || null)
            setNotification({ message: "Encryption key generated. Store the downloaded private key safely.", statusCode: response.status })
        } catch (err) {
            setNotification({ message: "Failed to generate encryption key", statusCode: 500 })
            console.error(err)
        } finally {
            setKeyLoading(false)
        }
    }

    const handleSaveSettings = async () => {
        const retentionDays = Number(logRetentionDays)
        const maxLogRows = Number(logSize)
        if (!Number.isFinite(retentionDays) || retentionDays < 1 || !Number.isFinite(maxLogRows) || maxLogRows < 1) {
            setNotification({ message: "Log retention and max log rows must be positive numbers", statusCode: 400 })
            return
        }

        setSettingsLoading(true)
        setNotification(null)
        try {
            const response = await post("users/settings", {
                log_retention_period_d: retentionDays,
                log_size: maxLogRows,
                compression_enabled: compressionEnabled,
                encryption_enabled: encryptionEnabled,
                gotify_enabled: gotifyEnabled,
                gotify_url: gotifyUrl || null,
                gotify_token: gotifyToken || null,
            })

            if (response.status >= 400) {
                setNotification({ message: response.detail || "Failed to save settings", statusCode: response.status })
                return
            }

            setNotification({ message: response.message || "Settings saved successfully", statusCode: response.status })
            setGotifyToken("")
            if (gotifyToken) setGotifyTokenConfigured(true)
            await loadUserInfo()
        } catch (err) {
            setNotification({ message: "Failed to save settings", statusCode: 500 })
            console.error(err)
        } finally {
            setSettingsLoading(false)
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
                                    <Group justify="space-between" pt="sm" style={{ borderTop: "1px solid var(--lnr-border)" }}>
                                        <div>
                                            <Text fw={600} size="sm">Appearance</Text>
                                            <Text size="xs" c="dimmed">
                                                Current mode: {colorScheme === "dark" ? "Black" : "Light"}
                                            </Text>
                                        </div>
                                        <Button
                                            leftSection={
                                                colorScheme === "dark"
                                                    ? <IconSun size={16} stroke={1.5} />
                                                    : <IconMoon size={16} stroke={1.5} />
                                            }
                                            onClick={() => toggleColorScheme()}
                                            variant="light"
                                            size="xs"
                                        >
                                            {colorScheme === "dark" ? "Light mode" : "Black mode"}
                                        </Button>
                                    </Group>
                                </Stack>
                            </Paper>

                            <Paper p="md" withBorder>
                                <Stack gap="md">
                                    <div>
                                        <Text fw={600} size="sm">Operational Settings</Text>
                                        <Text size="xs" c="dimmed">
                                            Tenant-wide defaults for log cleanup, backup artifacts, encryption, and Gotify notifications.
                                        </Text>
                                    </div>

                                    <Group grow align="flex-start">
                                        <NumberInput
                                            label="Log retention days"
                                            min={1}
                                            value={logRetentionDays}
                                            onChange={setLogRetentionDays}
                                        />
                                        <NumberInput
                                            label="Max stored log rows"
                                            min={1}
                                            thousandSeparator=","
                                            value={logSize}
                                            onChange={setLogSize}
                                        />
                                    </Group>

                                    <Divider />

                                    <Switch
                                        label="Compress backups before upload"
                                        checked={compressionEnabled}
                                        onChange={(event) => setCompressionEnabled(event.currentTarget.checked)}
                                    />

                                    <Group justify="space-between" align="flex-start">
                                        <Switch
                                            label="Encrypt backups"
                                            description={encryptionKeyConfigured ? `Public key configured${keyFingerprint ? `: ${keyFingerprint.slice(0, 12)}...` : ""}` : "Generate a key before enabling encryption."}
                                            checked={encryptionEnabled}
                                            onChange={(event) => setEncryptionEnabled(event.currentTarget.checked)}
                                        />
                                        <Button
                                            variant="light"
                                            onClick={handleGenerateEncryptionKey}
                                            loading={keyLoading}
                                        >
                                            Generate encryption key
                                        </Button>
                                    </Group>

                                    <Alert color="yellow" title="Private key warning">
                                        The private key is downloaded only during generation and is never stored on the server. You will need it to restore encrypted backups.
                                    </Alert>

                                    <Divider />

                                    <Switch
                                        label="Enable Gotify notifications"
                                        description="Notifications are sent on backup failure, restore failure, and restore success."
                                        checked={gotifyEnabled}
                                        onChange={(event) => setGotifyEnabled(event.currentTarget.checked)}
                                    />
                                    {gotifyEnabled && (
                                        <Group grow align="flex-start">
                                            <TextInput
                                                label="Gotify URL"
                                                placeholder="https://gotify.example.com"
                                                value={gotifyUrl}
                                                onChange={(event) => setGotifyUrl(event.currentTarget.value)}
                                            />
                                            <PasswordInput
                                                label="Gotify token"
                                                placeholder={gotifyTokenConfigured ? "Configured - enter to replace" : "Enter token"}
                                                value={gotifyToken}
                                                onChange={(event) => setGotifyToken(event.currentTarget.value)}
                                            />
                                        </Group>
                                    )}

                                    <Button onClick={handleSaveSettings} loading={settingsLoading}>
                                        Save Settings
                                    </Button>
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
                            onClick={() => loadLogs()}
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
