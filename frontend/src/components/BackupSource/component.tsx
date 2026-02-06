"use client"
import { post, get, del } from "@/lib/backendRequests"
import { useState, useEffect, useCallback } from "react"
import {
    Select,
    Stack,
    Modal,
    TextInput,
    NumberInput,
    Button,
    Group,
    Table,
    Loader,
    ActionIcon,
    Tabs
} from "@mantine/core"
import {
    IconEdit,
    IconTrash,
    IconPlus,
    IconRefresh,
    IconCheck,
    IconDatabase,
    IconSearch,
    IconLock,
    IconBox
} from "@tabler/icons-react"
import { DisplayNotification } from "../Notifications/component"

const SOURCE_TYPES = ["postgres", "elasticsearch", "vault", "qdrant"]

interface Credentials {
    url: string
    login?: string | null  // Changed from 'username' to 'login' to match backend
    password?: string | null
    apiKey?: string | null  // Changed from 'api_key' to 'apiKey' (camelCase)
}

interface BackupSource {
    id: number
    source_type: string
    name: string
    url: string
    login?: string | null
    password?: string | null
    api_key?: string | null
    created_at: string
    updated_at: string
}

interface NotificationState {
    message: string
    statusCode: number
}


interface CredentialComponentProps {
    onCredentialsChange: (credentials: Credentials) => void
    initialValues: BackupSource | null
}

const splitHostPort = (url?: string) => {
    if (!url) return { host: "", port: undefined }
    const match = url.match(/([^:]+):(\d+)/)
    return {
        host: match?.[1] ?? "",
        port: match?.[2] ? parseInt(match[2]) : undefined
    }
}



function ExportPostgresCredentials({ onCredentialsChange, initialValues }: CredentialComponentProps) {
    const [host, setHost] = useState("")
    const [port, setPort] = useState<number | undefined>()
    const [database, setDatabase] = useState("")
    const [username, setUsername] = useState("")
    const [password, setPassword] = useState("")

    // Initialize from existing source
    useEffect(() => {
        if (!initialValues) {
            setHost("")
            setPort(undefined)
            setDatabase("")
            setUsername("")
            setPassword("")
            return
        }

        const match = initialValues.url?.match(/postgres:\/\/([^:]+):(\d+)\/(.+)/)
        if (match) {
            setHost(match[1])
            setPort(parseInt(match[2]))
            setDatabase(match[3])
        }

        setUsername(initialValues.login || "")
        // Note: password won't be available when editing (it's encrypted on backend)
        setPassword("")
    }, [initialValues])

    // Update parent whenever fields change
    useEffect(() => {
        const credentials: Credentials = {
            url:
                host && port && database
                    ? `postgres://${host}:${port}/${database}`
                    : "",
            login: username || null,
            password: password || null,
            apiKey: null
        }
        onCredentialsChange(credentials)
    }, [host, port, database, username, password, onCredentialsChange])

    return (
        <Stack>
            <TextInput 
                label="Host" 
                value={host} 
                onChange={(e) => setHost(e.currentTarget.value)}
                required
            />
            <NumberInput 
                label="Port" 
                value={port} 
                onChange={(v) => setPort(typeof v === "number" ? v : undefined)}
                required
            />
            <TextInput 
                label="Database" 
                value={database} 
                onChange={(e) => setDatabase(e.currentTarget.value)}
                required
            />
            <TextInput 
                label="Username" 
                value={username} 
                onChange={(e) => setUsername(e.currentTarget.value)}
                required
            />
            <TextInput 
                type="password" 
                label="Password" 
                value={password} 
                onChange={(e) => setPassword(e.currentTarget.value)}
                placeholder={initialValues ? "Leave blank to keep existing" : ""}
                required={!initialValues}
            />
        </Stack>
    )
}



function ExportQdrantCredentials({ onCredentialsChange, initialValues }: CredentialComponentProps) {
    const [host, setHost] = useState("")
    const [port, setPort] = useState<number | undefined>()
    const [apiKey, setApiKey] = useState("")

    useEffect(() => {
        if (!initialValues) {
            setHost("")
            setPort(undefined)
            setApiKey("")
            return
        }
        const { host, port } = splitHostPort(initialValues.url)
        setHost(host)
        setPort(port)
        // Note: api_key won't be available when editing (it's encrypted on backend)
        setApiKey("")
    }, [initialValues])

    useEffect(() => {
        const credentials: Credentials = {
            url: host && port ? `${host}:${port}` : "",
            login: null,
            password: null,
            apiKey: apiKey || null
        }
        onCredentialsChange(credentials)
    }, [host, port, apiKey, onCredentialsChange])

    return (
        <Stack>
            <TextInput 
                label="Host" 
                value={host} 
                onChange={(e) => setHost(e.currentTarget.value)}
                required
            />
            <NumberInput 
                label="Port" 
                value={port} 
                onChange={(v) => setPort(typeof v === "number" ? v : undefined)}
                required
            />
            <TextInput 
                label="API Key (optional)" 
                value={apiKey} 
                onChange={(e) => setApiKey(e.currentTarget.value)}
                placeholder={initialValues ? "Leave blank to keep existing" : ""}
            />
        </Stack>
    )
}



function ExportElasticsearchCredentials({ onCredentialsChange, initialValues }: CredentialComponentProps) {
    const [host, setHost] = useState("")
    const [port, setPort] = useState<number | undefined>()
    const [apiKey, setApiKey] = useState("")
    const [username, setUsername] = useState("")
    const [password, setPassword] = useState("")

    useEffect(() => {
        if (!initialValues) {
            setHost("")
            setPort(undefined)
            setApiKey("")
            setUsername("")
            setPassword("")
            return
        }
        const { host, port } = splitHostPort(initialValues.url)
        setHost(host)
        setPort(port)
        // Note: encrypted fields won't be available when editing
        setApiKey("")
        setUsername(initialValues.login || "")
        setPassword("")
    }, [initialValues])

    useEffect(() => {
        const credentials: Credentials = {
            url: host && port ? `${host}:${port}` : "",
            login: username || null,
            password: password || null,
            apiKey: apiKey || null
        }
        onCredentialsChange(credentials)
    }, [host, port, username, password, apiKey, onCredentialsChange])

    return (
        <Stack>
            <TextInput 
                label="Host" 
                value={host} 
                onChange={(e) => setHost(e.currentTarget.value)}
                required
            />
            <NumberInput 
                label="Port" 
                value={port} 
                onChange={(v) => setPort(typeof v === "number" ? v : undefined)}
                required
            />
            <TextInput 
                label="API Key" 
                value={apiKey} 
                onChange={(e) => setApiKey(e.currentTarget.value)}
                placeholder={initialValues ? "Leave blank to keep existing" : ""}
            />
            <TextInput 
                label="Username" 
                value={username} 
                onChange={(e) => setUsername(e.currentTarget.value)}
            />
            <TextInput 
                type="password" 
                label="Password" 
                value={password} 
                onChange={(e) => setPassword(e.currentTarget.value)}
                placeholder={initialValues ? "Leave blank to keep existing" : ""}
            />
        </Stack>
    )
}



function ExportVaultCredentials({ onCredentialsChange, initialValues }: CredentialComponentProps) {
    const [host, setHost] = useState("")
    const [port, setPort] = useState<number | undefined>()
    const [apiKey, setApiKey] = useState("")

    useEffect(() => {
        if (!initialValues) {
            setHost("")
            setPort(undefined)
            setApiKey("")
            return
        }
        const { host, port } = splitHostPort(initialValues.url)
        setHost(host)
        setPort(port)
        // Note: api_key won't be available when editing (it's encrypted on backend)
        setApiKey("")
    }, [initialValues])

    useEffect(() => {
        const credentials: Credentials = {
            url: host && port ? `${host}:${port}` : "",
            login: null,
            password: null,
            apiKey: apiKey || null
        }
        onCredentialsChange(credentials)
    }, [host, port, apiKey, onCredentialsChange])

    return (
        <Stack>
            <TextInput 
                label="Host" 
                value={host} 
                onChange={(e) => setHost(e.currentTarget.value)}
                required
            />
            <NumberInput 
                label="Port" 
                value={port} 
                onChange={(v) => setPort(typeof v === "number" ? v : undefined)}
                required
            />
            <TextInput 
                label="API Key" 
                value={apiKey} 
                onChange={(e) => setApiKey(e.currentTarget.value)}
                placeholder={initialValues ? "Leave blank to keep existing" : ""}
                required={!initialValues}
            />
        </Stack>
    )
}



export function BackupSourcesManager() {
    const [activeTab, setActiveTab] = useState<string | null>("postgres")
    const [modalOpened, setModalOpened] = useState(false)
    const [sourceType, setSourceType] = useState<string>("postgres")
    const [sourceName, setSourceName] = useState<string>("")
    const [credentials, setCredentials] = useState<Credentials>({
        url: "",
        login: null,
        password: null,
        apiKey: null
    })
    const [loading, setLoading] = useState(false)
    const [sources, setSources] = useState<BackupSource[]>([])
    const [loadingSources, setLoadingSources] = useState(false)
    const [notification, setNotification] = useState<NotificationState | null>(null)
    const [editingId, setEditingId] = useState<number | null>(null)
    const [editingSource, setEditingSource] = useState<BackupSource | null>(null)

    // Fetch backup sources
    const fetchSources = async () => {
        setLoadingSources(true)
        setNotification(null)
        try {
            const response = await get("backup-sources/list")
            
            if (response.status >= 400) {
                setNotification({ 
                    message: response.detail || "Failed to fetch backup sources", 
                    statusCode: response.status 
                })
                return
            }

            const backupSources = response.data?.backup_sources
            if (Array.isArray(backupSources)) {
                setSources(backupSources)
            }
        } catch (err) {
            setNotification({ message: "Failed to fetch backup sources", statusCode: 500 })
            console.error(err)
        } finally {
            setLoadingSources(false)
        }
    }

    useEffect(() => {
        fetchSources()
    }, [])

    // Memoize credentials handler to prevent unnecessary re-renders
    const handleCredentialsChange = useCallback((newCredentials: Credentials) => {
        console.log("Credentials updated:", newCredentials)
        setCredentials(newCredentials)
    }, [])

    const getCredentialsComponent = () => {
        const props = { 
            onCredentialsChange: handleCredentialsChange, 
            initialValues: editingSource 
        }
        switch (sourceType) {
            case "postgres":
                return <ExportPostgresCredentials {...props} />
            case "qdrant":
                return <ExportQdrantCredentials {...props} />
            case "elasticsearch":
                return <ExportElasticsearchCredentials {...props} />
            case "vault":
                return <ExportVaultCredentials {...props} />
            default:
                return null
        }
    }

    const getFilteredSources = (type: string) => {
        return sources.filter(s => s.source_type === type)
    }

    const handleAddSource = async () => {
        // Validate credentials
        if (!credentials.url) {
            setNotification({ message: "Please fill in all required credentials", statusCode: 400 })
            return
        }

        setLoading(true)
        setNotification(null)
        try {
            const payload = {
                source_type: sourceType,
                source_name: sourceName || undefined,
                credentials: {
                    url: credentials.url,
                    login: credentials.login || null,
                    password: credentials.password || null,
                    api_key: credentials.apiKey || null  // Convert camelCase to snake_case for backend
                }
            }

            console.log("Sending payload:", JSON.stringify(payload, null, 2))

            const response = await post("backup-sources/add", payload)
            
            if (response.status >= 400) {
                setNotification({ 
                    message: response.detail || "Failed to add backup source", 
                    statusCode: response.status 
                })
                return
            }

            setNotification({ 
                message: response.message || "Backup source added successfully", 
                statusCode: response.status 
            })
            
            // Reset form
            setModalOpened(false)
            setSourceName("")
            setCredentials({
                url: "",
                login: null,
                password: null,
                apiKey: null
            })
            setSourceType("postgres")
            setEditingId(null)
            setEditingSource(null)
            
            await fetchSources()
        } catch (err) {
            setNotification({ message: "Failed to add backup source", statusCode: 500 })
            console.error(err)
        } finally {
            setLoading(false)
        }
    }

    const handleUpdateSource = async (sourceId: number) => {
        if (!credentials.url) {
            setNotification({ message: "Please fill in required credentials", statusCode: 400 })
            return
        }

        setLoading(true)
        setNotification(null)
        try {
            // Only include fields that have values (allow keeping existing encrypted fields)
            const credentialsToSend: any = {
                url: credentials.url
            }
            
            if (credentials.login !== null && credentials.login !== undefined && credentials.login !== "") {
                credentialsToSend.login = credentials.login
            }
            
            if (credentials.password !== null && credentials.password !== undefined && credentials.password !== "") {
                credentialsToSend.password = credentials.password
            }
            
            if (credentials.apiKey !== null && credentials.apiKey !== undefined && credentials.apiKey !== "") {
                credentialsToSend.api_key = credentials.apiKey
            }

            const payload = {
                source_id: sourceId,
                source_name: sourceName || undefined,
                credentials: credentialsToSend
            }

            console.log("Updating with payload:", JSON.stringify(payload, null, 2))

            const response = await post("backup-sources/update", payload)
            
            if (response.status >= 400) {
                setNotification({ 
                    message: response.detail || "Failed to update backup source", 
                    statusCode: response.status 
                })
                return
            }

            setNotification({ 
                message: response.message || "Backup source updated successfully", 
                statusCode: response.status 
            })
            
            // Reset form
            setModalOpened(false)
            setEditingId(null)
            setEditingSource(null)
            setSourceName("")
            setCredentials({
                url: "",
                login: null,
                password: null,
                apiKey: null
            })
            
            await fetchSources()
        } catch (err) {
            setNotification({ message: "Failed to update backup source", statusCode: 500 })
            console.error(err)
        } finally {
            setLoading(false)
        }
    }

    const handleDeleteSource = async (sourceId: number) => {
        if (!window.confirm("Are you sure you want to delete this backup source?")) return

        setNotification(null)
        try {
            const response = await del(`backup-sources/delete?source_id=${sourceId}`)
            
            if (response.status >= 400) {
                setNotification({ 
                    message: response.detail || "Failed to delete backup source", 
                    statusCode: response.status 
                })
                return
            }

            setNotification({ 
                message: response.message || "Backup source deleted successfully", 
                statusCode: response.status 
            })
            await fetchSources()
        } catch (err) {
            setNotification({ message: "Failed to delete backup source", statusCode: 500 })
            console.error(err)
        }
    }

    const handleTestConnection = async (sourceId: number) => {
        setNotification(null)
        try {
            const response = await get(`backup-sources/test-connection?source_id=${sourceId}`)
            
            if (response.status >= 400) {
                setNotification({ 
                    message: response.detail || "Connection test failed", 
                    statusCode: response.status 
                })
                return
            }

            setNotification({ 
                message: response.message || "Connection successful", 
                statusCode: response.status 
            })
        } catch (err) {
            setNotification({ message: "Connection test failed", statusCode: 500 })
            console.error(err)
        }
    }

    const openAddModal = () => {
        setEditingId(null)
        setEditingSource(null)
        setSourceName("")
        setCredentials({
            url: "",
            login: null,
            password: null,
            apiKey: null
        })
        setSourceType(activeTab || "postgres")
        setModalOpened(true)
    }

    const openEditModal = (source: BackupSource) => {
        setEditingId(source.id)
        setEditingSource(source)
        setSourceName(source.name)
        setSourceType(source.source_type)
        // Reset credentials - they will be populated by the credential component's useEffect
        setCredentials({
            url: "",
            login: null,
            password: null,
            apiKey: null
        })
        setModalOpened(true)
    }

    const isFormValid = () => {
        if (!sourceName || !credentials.url) return false
        
        // Additional validation based on source type
        switch (sourceType) {
            case "postgres":
                return !!(credentials.login && (editingId || credentials.password))
            case "vault":
                return !!(editingId || credentials.apiKey)
            case "qdrant":
            case "elasticsearch":
                return true
            default:
                return true
        }
    }

    const SourceTable = ({ sources }: { sources: BackupSource[] }) => (
        <Table striped>
            <Table.Thead>
                <Table.Tr>
                    <Table.Th>Name</Table.Th>
                    <Table.Th>URL</Table.Th>
                    <Table.Th>Created</Table.Th>
                    <Table.Th>Actions</Table.Th>
                </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
                {sources.length === 0 ? (
                    <Table.Tr>
                        <Table.Td colSpan={4} style={{ textAlign: "center", color: "#999" }}>
                            No sources configured
                        </Table.Td>
                    </Table.Tr>
                ) : (
                    sources.map((source) => (
                        <Table.Tr key={source.id}>
                            <Table.Td>{source.name}</Table.Td>
                            <Table.Td style={{ fontSize: 12 }}>{source.url}</Table.Td>
                            <Table.Td style={{ fontSize: 12 }}>
                                {new Date(source.created_at).toLocaleDateString()}
                            </Table.Td>
                            <Table.Td>
                                <Group gap={8}>
                                    <ActionIcon 
                                        size="sm"
                                        variant="default"
                                        onClick={() => handleTestConnection(source.id)}
                                        title="Test Connection"
                                    >
                                        <IconCheck size={16} />
                                    </ActionIcon>
                                    <ActionIcon 
                                        size="sm"
                                        variant="default"
                                        onClick={() => openEditModal(source)}
                                        title="Edit Source"
                                    >
                                        <IconEdit size={16} />
                                    </ActionIcon>
                                    <ActionIcon 
                                        color="red" 
                                        variant="subtle"
                                        onClick={() => handleDeleteSource(source.id)}
                                        title="Delete Source"
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
                <h1>Backup Sources</h1>
                <Button 
                    leftSection={<IconPlus size={16} />}
                    onClick={openAddModal}
                >
                    Add Source
                </Button>
                <ActionIcon 
                    onClick={fetchSources} 
                    loading={loadingSources} 
                    variant="default"
                >
                    <IconRefresh size={16} />
                </ActionIcon>
            </Group>

            {notification && (
                <DisplayNotification 
                    message={notification.message} 
                    statusCode={notification.statusCode} 
                />
            )}

            {loadingSources ? (
                <Loader />
            ) : (
                <Tabs value={activeTab} onChange={setActiveTab}>
                    <Tabs.List>
                        <Tabs.Tab value="postgres" leftSection={<IconDatabase size={14} />}>
                            PostgreSQL ({getFilteredSources("postgres").length})
                        </Tabs.Tab>
                        <Tabs.Tab value="elasticsearch" leftSection={<IconSearch size={14} />}>
                            Elasticsearch ({getFilteredSources("elasticsearch").length})
                        </Tabs.Tab>
                        <Tabs.Tab value="vault" leftSection={<IconLock size={14} />}>
                            Vault ({getFilteredSources("vault").length})
                        </Tabs.Tab>
                        <Tabs.Tab value="qdrant" leftSection={<IconBox size={14} />}>
                            Qdrant ({getFilteredSources("qdrant").length})
                        </Tabs.Tab>
                    </Tabs.List>

                    <Tabs.Panel value="postgres" pt="md">
                        <SourceTable sources={getFilteredSources("postgres")} />
                    </Tabs.Panel>
                    <Tabs.Panel value="elasticsearch" pt="md">
                        <SourceTable sources={getFilteredSources("elasticsearch")} />
                    </Tabs.Panel>
                    <Tabs.Panel value="vault" pt="md">
                        <SourceTable sources={getFilteredSources("vault")} />
                    </Tabs.Panel>
                    <Tabs.Panel value="qdrant" pt="md">
                        <SourceTable sources={getFilteredSources("qdrant")} />
                    </Tabs.Panel>
                </Tabs>
            )}

            <Modal 
                opened={modalOpened} 
                onClose={() => {
                    setModalOpened(false)
                    setEditingId(null)
                    setEditingSource(null)
                }}
                title={editingId ? "Edit Backup Source" : "Add Backup Source"}
                size="lg"
            >
                <Stack>
                    {!editingId && (
                        <Select
                            data={SOURCE_TYPES}
                            searchable
                            value={sourceType}
                            label="Source Type"
                            onChange={(value) => setSourceType(value || "postgres")}
                            required
                        />
                    )}

                    <TextInput
                        label="Source Name"
                        value={sourceName}
                        onChange={(e) => setSourceName(e.currentTarget.value)}
                        placeholder="e.g., Production DB"
                        required
                    />

                    {getCredentialsComponent()}

                    <Group mt={20}>
                        <Button
                            onClick={() => editingId ? handleUpdateSource(editingId) : handleAddSource()}
                            disabled={!isFormValid()}
                            loading={loading}
                        >
                            {editingId ? "Update" : "Add"} Source
                        </Button>
                        <Button 
                            variant="default" 
                            onClick={() => {
                                setModalOpened(false)
                                setEditingId(null)
                                setEditingSource(null)
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