"use client"
import { post, get, del, put } from "@/lib/backendRequests"
import { useState, useEffect } from "react"
import { Select, Stack, Modal, TextInput, NumberInput, Button, Group, Table, Alert, Loader, ActionIcon, Tabs } from "@mantine/core"
import { IconEdit, IconTrash, IconPlus, IconRefresh, IconCheck, IconDatabase, IconSearch, IconLock, IconBox } from "@tabler/icons-react"
import { DisplayNotification } from "../Notifications/component"

const SOURCE_TYPES = ["postgres", "elasticsearch", "vault", "qdrant"]

interface Credentials {
    url: string
    username?: string | null
    password?: string | null
    apiKey?: string | null
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

function ExportPostgresCredentials({ onCredentialsChange, initialValues }: { onCredentialsChange: (creds: Credentials) => void, initialValues?: BackupSource | null }) {
    const [host, setHost] = useState<string>("")
    const [port, setPort] = useState<number | undefined>(undefined)
    const [username, setUsername] = useState<string>("")
    const [password, setPassword] = useState<string>("")
    const [database, setDatabase] = useState<string>("")

    useEffect(() => {
        if (initialValues?.url) {
            const url = initialValues.url
            const match = url.match(/postgres:\/\/([^:]+):(\d+)\/(.+)/)
            if (match) {
                setHost(match[1])
                setPort(parseInt(match[2]))
                setDatabase(match[3])
            }
            if (initialValues.login) setUsername(initialValues.login)
            if (initialValues.password) setPassword(initialValues.password)
        }
    }, [initialValues])

    const formatConnString = (host: string, port: number, database: string) => {
        return "postgres://" + host + ":" + port + "/" + database
    }

    const handleChange = () => {
        if (host && port && database && username && password) {
            onCredentialsChange({
                url: formatConnString(host, port, database),
                username,
                password,
                apiKey: null
            })
        }
    }

    useEffect(() => {
        handleChange()
    }, [host, port, username, password, database])

    return (
        <Stack>
            <TextInput label="Host" value={host} onChange={(e) => setHost(e.currentTarget.value)} placeholder="localhost" />
            <NumberInput label="Port" value={port} onChange={(value) => setPort(typeof value === 'number' ? value : undefined)} placeholder="5432" />
            <TextInput label="Database" value={database} onChange={(e) => setDatabase(e.currentTarget.value)} placeholder="mydb" />
            <TextInput label="Username" value={username} onChange={(e) => setUsername(e.currentTarget.value)} />
            <TextInput label="Password" type="password" value={password} onChange={(e) => setPassword(e.currentTarget.value)} />
        </Stack>
    )
}

function ExportQdrantCredentials({ onCredentialsChange, initialValues }: { onCredentialsChange: (creds: Credentials) => void, initialValues?: BackupSource | null }) {
    const [host, setHost] = useState<string>("")
    const [port, setPort] = useState<number | undefined>(undefined)
    const [apiKey, setApiKey] = useState<string>("")

    useEffect(() => {
        if (initialValues?.url) {
            const url = initialValues.url
            const match = url.match(/([^:]+):(\d+)/)
            if (match) {
                setHost(match[1])
                setPort(parseInt(match[2]))
            }
            if (initialValues.api_key) setApiKey(initialValues.api_key)
        }
    }, [initialValues])

    useEffect(() => {
        if (host && port) {
            onCredentialsChange({
                url: host + ":" + port,
                username: null,
                password: null,
                apiKey: apiKey || null
            })
        }
    }, [host, port, apiKey, onCredentialsChange])

    return (
        <Stack>
            <TextInput label="Host" value={host} onChange={(e) => setHost(e.currentTarget.value)} placeholder="localhost" />
            <NumberInput label="Port" value={port} onChange={(value) => setPort(typeof value === 'number' ? value : undefined)} placeholder="6333" />
            <TextInput label="Api Key (optional)" value={apiKey} onChange={(e) => setApiKey(e.currentTarget.value)} />
        </Stack>
    )
}

function ExportElasticsearchCredentials({ onCredentialsChange, initialValues }: { onCredentialsChange: (creds: Credentials) => void, initialValues?: BackupSource | null }) {
    const [host, setHost] = useState<string>("")
    const [port, setPort] = useState<number | undefined>(undefined)
    const [apiKey, setApiKey] = useState<string>("")
    const [username, setUsername] = useState<string>("")
    const [password, setPassword] = useState<string>("")

    useEffect(() => {
        if (initialValues?.url) {
            const url = initialValues.url
            const match = url.match(/([^:]+):(\d+)/)
            if (match) {
                setHost(match[1])
                setPort(parseInt(match[2]))
            }
            if (initialValues.login) setUsername(initialValues.login)
            if (initialValues.password) setPassword(initialValues.password)
            if (initialValues.api_key) setApiKey(initialValues.api_key)
        }
    }, [initialValues])

    useEffect(() => {
        if (host && port && (apiKey || (username && password))) {
            onCredentialsChange({
                url: host + ":" + port,
                username: username || null,
                password: password || null,
                apiKey: apiKey || null
            })
        }
    }, [host, port, apiKey, username, password, onCredentialsChange])

    return (
        <Stack>
            <TextInput label="Host" value={host} onChange={(e) => setHost(e.currentTarget.value)} placeholder="localhost" />
            <NumberInput label="Port" value={port} onChange={(value) => setPort(typeof value === 'number' ? value : undefined)} placeholder="9200" />
            <TextInput label="Api Key" value={apiKey} onChange={(e) => setApiKey(e.currentTarget.value)} />
            <TextInput label="Username" value={username} onChange={(e) => setUsername(e.currentTarget.value)} />
            <TextInput label="Password" type="password" value={password} onChange={(e) => setPassword(e.currentTarget.value)} />
        </Stack>
    )
}

function ExportVaultCredentials({ onCredentialsChange, initialValues }: { onCredentialsChange: (creds: Credentials) => void, initialValues?: BackupSource | null }) {
    const [host, setHost] = useState<string>("")
    const [port, setPort] = useState<number | undefined>(undefined)
    const [apiKey, setApiKey] = useState<string>("")

    useEffect(() => {
        if (initialValues?.url) {
            const url = initialValues.url
            const match = url.match(/([^:]+):(\d+)/)
            if (match) {
                setHost(match[1])
                setPort(parseInt(match[2]))
            }
            if (initialValues.api_key) setApiKey(initialValues.api_key)
        }
    }, [initialValues])

    useEffect(() => {
        if (host && port && apiKey) {
            onCredentialsChange({
                url: host + ":" + port,
                username: null,
                password: null,
                apiKey
            })
        }
    }, [host, port, apiKey, onCredentialsChange])

    return (
        <Stack>
            <TextInput label="Host" value={host} onChange={(e) => setHost(e.currentTarget.value)} placeholder="localhost" />
            <NumberInput label="Port" value={port} onChange={(value) => setPort(typeof value === 'number' ? value : undefined)} placeholder="8200" />
            <TextInput label="Api Key" value={apiKey} onChange={(e) => setApiKey(e.currentTarget.value)} />
        </Stack>
    )
}

export function BackupSourcesManager() {
    const [activeTab, setActiveTab] = useState<string | null>("postgres")
    const [modalOpened, setModalOpened] = useState(false)
    const [sourceType, setSourceType] = useState<string>("postgres")
    const [sourceName, setSourceName] = useState<string>("")
    const [credentials, setCredentials] = useState<Credentials | null>(null)
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
                setNotification({ message: response.detail|| "Failed to fetch backup sources", statusCode: response.status })
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

    const getCredentialsComponent = () => {
        const props = { onCredentialsChange: setCredentials, initialValues: editingSource }
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

    const getSourceIcon = (type: string) => {
        switch (type) {
            case "postgres":
                return <IconDatabase size={16} />
            case "elasticsearch":
                return <IconSearch size={16} />
            case "vault":
                return <IconLock size={16} />
            case "qdrant":
                return <IconBox size={16} />
            default:
                return null
        }
    }

    const handleAddSource = async () => {
        if (!credentials) {
            setNotification({ message: "Please fill in all credentials", statusCode: 400 })
            return
        }

        setLoading(true)
        setNotification(null)
        try {
            const payload = {
                source_type: sourceType,
                source_name: sourceName || undefined,
                credentials
            }

            const response = await post("backup-sources/add", payload)
            
            if (response.status >= 400) {
                setNotification({ message: response.detail|| "Failed to add backup source", statusCode: response.status })
                return
            }

            setNotification({ message: response.message || "Backup source added successfully", statusCode: response.status })
            setModalOpened(false)
            setSourceName("")
            setCredentials(null)
            setSourceType("postgres")
            await fetchSources()
        } catch (err) {
            setNotification({ message: "Failed to add backup source", statusCode: 500 })
            console.error(err)
        } finally {
            setLoading(false)
        }
    }

    const handleUpdateSource = async (sourceId: number) => {
        if (!credentials) {
            setNotification({ message: "Please fill in credentials", statusCode: 400 })
            return
        }

        setLoading(true)
        setNotification(null)
        try {
            const payload = {
                source_id: sourceId,
                source_name: sourceName || undefined,
                credentials
            }

            const response = await post("backup-sources/update", payload)
            
            if (response.status >= 400) {
                setNotification({ message: response.detail|| "Failed to update backup source", statusCode: response.status })
                return
            }

            setNotification({ message: response.message || "Backup source updated successfully", statusCode: response.status })
            setModalOpened(false)
            setEditingId(null)
            setEditingSource(null)
            setSourceName("")
            setCredentials(null)
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
                setNotification({ message: response.detail|| "Failed to delete backup source", statusCode: response.status })
                return
            }

            setNotification({ message: response.message || "Backup source deleted successfully", statusCode: response.status })
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
                setNotification({ message: response.detail|| "Connection test failed", statusCode: response.status })
                return
            }

            setNotification({ message: response.message || "Connection successful", statusCode: response.status })
        } catch (err) {
            setNotification({ message: "Connection test failed", statusCode: 500 })
            console.error(err)
        }
    }

    const isFormValid = sourceName && credentials

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
                            <Table.Td style={{ fontSize: 12 }}>{new Date(source.created_at).toLocaleDateString()}</Table.Td>
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
                                        onClick={() => {
                                            setEditingId(source.id)
                                            setEditingSource(source)
                                            setSourceName(source.name)
                                            setSourceType(source.source_type)
                                            setCredentials(null)
                                            setModalOpened(true)
                                        }}
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
                    onClick={() => {
                        setEditingId(null)
                        setEditingSource(null)
                        setSourceName("")
                        setCredentials(null)
                        setSourceType(activeTab || "postgres")
                        setModalOpened(true)
                    }}
                >
                    Add Source
                </Button>
                <ActionIcon onClick={fetchSources} loading={loadingSources} variant="default">
                    <IconRefresh size={16} />
                </ActionIcon>
            </Group>

            {notification && <DisplayNotification message={notification.message} statusCode={notification.statusCode} />}

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
                onClose={() => setModalOpened(false)}
                title={editingId ? "Edit Backup Source" : "Add Backup Source"}
            >
                <Stack>
                    {!editingId && (
                        <Select
                            data={SOURCE_TYPES}
                            searchable
                            value={sourceType}
                            defaultValue="postgres"
                            label="Source Type"
                            onChange={(value) => setSourceType(value || "postgres")}
                        />
                    )}

                    <TextInput
                        label="Source Name"
                        value={sourceName}
                        onChange={(e) => setSourceName(e.currentTarget.value)}
                        placeholder="e.g., Production DB"
                    />

                    {getCredentialsComponent()}

                    <Group mt={20}>
                        <Button
                            onClick={() => editingId ? handleUpdateSource(editingId) : handleAddSource()}
                            disabled={!isFormValid}
                            loading={loading}
                        >
                            {editingId ? "Update" : "Add"} Source
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