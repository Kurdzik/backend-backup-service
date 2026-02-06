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
    IconCloudUpload,
    IconFolder,
    IconNetwork,
    IconServer
} from "@tabler/icons-react"
import { DisplayNotification } from "../Notifications/component"

const DESTINATION_TYPES = ["s3", "smb", "sftp", "local_fs"]
const LOCAL_FS_ROOT = "/mnt/backups"

interface Credentials {
    url: string
    login?: string | null
    password?: string | null
    api_key?: string | null
}

interface BackupDestination {
    id: number
    destination_type: string
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
    initialValues: BackupDestination | null
}



function DestinationS3Credentials({ onCredentialsChange, initialValues }: CredentialComponentProps) {
    const [endpointUrl, setEndpointUrl] = useState<string>("")
    const [bucketName, setBucketName] = useState<string>("")
    const [regionName, setRegionName] = useState<string>("")
    const [login, setLogin] = useState<string>("")
    const [password, setPassword] = useState<string>("")

    // Initialize from existing destination
    useEffect(() => {
        if (!initialValues) {
            setEndpointUrl("")
            setBucketName("")
            setRegionName("")
            setLogin("")
            setPassword("")
            return
        }

        const url = initialValues.url
        const match = url.match(/s3:\/\/([^/?]+)/)
        if (match) setBucketName(match[1])
        
        const endpointMatch = url.match(/endpoint_url=([^&]+)/)
        if (endpointMatch) setEndpointUrl(decodeURIComponent(endpointMatch[1]))
        
        const regionMatch = url.match(/region_name=([^&]+)/)
        if (regionMatch) setRegionName(decodeURIComponent(regionMatch[1]))
        
        setLogin(initialValues.login || "")
        setPassword(initialValues.password || "")
    }, [initialValues])

    // Update parent whenever fields change
    useEffect(() => {
        const credentials: Credentials = {
            url: bucketName && endpointUrl && regionName
                ? `s3://${bucketName}/?endpoint_url=${endpointUrl}&region_name=${regionName}`
                : "",
            login: login || null,
            password: password || null,
            api_key: null
        }
        onCredentialsChange(credentials)
    }, [bucketName, endpointUrl, regionName, login, password, onCredentialsChange])

    return (
        <Stack>
            <TextInput 
                label="Endpoint URL" 
                value={endpointUrl} 
                onChange={(e) => setEndpointUrl(e.currentTarget.value)} 
                placeholder="https://api.s3..."
                required
            />
            <TextInput 
                label="Bucket Name" 
                value={bucketName} 
                onChange={(e) => setBucketName(e.currentTarget.value)} 
                placeholder="backups"
                required
            />
            <TextInput 
                label="Region" 
                value={regionName} 
                onChange={(e) => setRegionName(e.currentTarget.value)} 
                placeholder="us-east"
                required
            />
            <TextInput 
                label="Access Key" 
                value={login} 
                onChange={(e) => setLogin(e.currentTarget.value)}
                required
            />
            <TextInput 
                label="Secret Key" 
                type="password" 
                value={password} 
                onChange={(e) => setPassword(e.currentTarget.value)}
                required
            />
        </Stack>
    )
}



function DestinationSmbCredentials({ onCredentialsChange, initialValues }: CredentialComponentProps) {
    const [url, setUrl] = useState<string>("")
    const [login, setLogin] = useState<string>("")
    const [password, setPassword] = useState<string>("")

    useEffect(() => {
        if (!initialValues) {
            setUrl("")
            setLogin("")
            setPassword("")
            return
        }

        setUrl(initialValues.url || "")
        setLogin(initialValues.login || "")
        setPassword(initialValues.password || "")
    }, [initialValues])

    useEffect(() => {
        const credentials: Credentials = {
            url: url || "",
            login: login || null,
            password: password || null,
            api_key: null
        }
        onCredentialsChange(credentials)
    }, [url, login, password, onCredentialsChange])

    return (
        <Stack>
            <TextInput 
                label="SMB Path" 
                value={url} 
                onChange={(e) => setUrl(e.currentTarget.value)} 
                placeholder="//server/share"
                required
            />
            <TextInput 
                label="Username" 
                value={login} 
                onChange={(e) => setLogin(e.currentTarget.value)}
                required
            />
            <TextInput 
                label="Password" 
                type="password" 
                value={password} 
                onChange={(e) => setPassword(e.currentTarget.value)}
                required
            />
        </Stack>
    )
}


function DestinationSftpCredentials({ onCredentialsChange, initialValues }: CredentialComponentProps) {
    const [path, setPath] = useState<string>("")
    const [login, setLogin] = useState<string>("")
    const [password, setPassword] = useState<string>("")

    useEffect(() => {
        if (!initialValues) {
            setPath("")
            setLogin("")
            setPassword("")
            return
        }

        const url = initialValues.url
        const pathMatch = url.match(/sftp:\/\/(.+)/)
        if (pathMatch) setPath(pathMatch[1])
        
        setLogin(initialValues.login || "")
        setPassword(initialValues.password || "")
    }, [initialValues])

    useEffect(() => {
        const credentials: Credentials = {
            url: path ? `sftp://${path}` : "",
            login: login || null,
            password: password || null,
            api_key: null
        }
        onCredentialsChange(credentials)
    }, [path, login, password, onCredentialsChange])

    return (
        <Stack>
            <TextInput 
                label="SFTP URL" 
                value={path} 
                onChange={(e) => setPath(e.currentTarget.value)} 
                placeholder="server/path"
                required
            />
            <TextInput 
                label="Username" 
                value={login} 
                onChange={(e) => setLogin(e.currentTarget.value)}
                required
            />
            <TextInput 
                label="Password" 
                type="password" 
                value={password} 
                onChange={(e) => setPassword(e.currentTarget.value)}
                required
            />
        </Stack>
    )
}


function DestinationFsStoreCredentials({ onCredentialsChange, initialValues }: CredentialComponentProps) {
    const [relativePath, setRelativePath] = useState<string>("")

    useEffect(() => {
        if (!initialValues) {
            setRelativePath("")
            return
        }

        const url = initialValues.url
        // Extract the relative path after /mnt/backups
        if (url.startsWith(LOCAL_FS_ROOT)) {
            const relative = url.substring(LOCAL_FS_ROOT.length)
            setRelativePath(relative.startsWith("/") ? relative.substring(1) : relative)
        }
    }, [initialValues])

    useEffect(() => {
        const fullUrl = relativePath ? `${LOCAL_FS_ROOT}/${relativePath}` : LOCAL_FS_ROOT
        const credentials: Credentials = {
            url: fullUrl,
            login: null,
            password: null,
            api_key: null
        }
        onCredentialsChange(credentials)
    }, [relativePath, onCredentialsChange])

    return (
        <Stack>
            <TextInput
                label="Relative Path"
                placeholder="relative/path"
                value={relativePath}
                onChange={(e) => setRelativePath(e.currentTarget.value)}
            />
            <div style={{ fontSize: 12, color: "#666" }}>
                Full path: {relativePath ? `${LOCAL_FS_ROOT}/${relativePath}` : LOCAL_FS_ROOT}
            </div>
        </Stack>
    )
}


export function BackupDestinationsManager() {
    const [activeTab, setActiveTab] = useState<string | null>("s3")
    const [modalOpened, setModalOpened] = useState(false)
    const [destinationType, setDestinationType] = useState<string>("s3")
    const [destinationName, setDestinationName] = useState<string>("")
    const [credentials, setCredentials] = useState<Credentials>({
        url: "",
        login: null,
        password: null,
        api_key: null
    })
    const [loading, setLoading] = useState(false)
    const [destinations, setDestinations] = useState<BackupDestination[]>([])
    const [loadingDestinations, setLoadingDestinations] = useState(false)
    const [notification, setNotification] = useState<NotificationState | null>(null)
    const [editingId, setEditingId] = useState<number | null>(null)
    const [editingDestination, setEditingDestination] = useState<BackupDestination | null>(null)

    // Fetch backup destinations
    const fetchDestinations = async () => {
        setLoadingDestinations(true)
        setNotification(null)
        try {
            const response = await get("backup-destinations/list")
            
            if (response.status >= 400) {
                setNotification({ 
                    message: response.detail || "Failed to fetch backup destinations", 
                    statusCode: response.status 
                })
                return
            }

            const backupDestinations = response?.data?.backup_destinations || []
            if (Array.isArray(backupDestinations)) {
                setDestinations(backupDestinations)
            }
        } catch (err) {
            setNotification({ message: "Failed to fetch backup destinations", statusCode: 500 })
            console.error(err)
        } finally {
            setLoadingDestinations(false)
        }
    }

    useEffect(() => {
        fetchDestinations()
    }, [])

    // Memoize credentials handler to prevent unnecessary re-renders
    const handleCredentialsChange = useCallback((newCredentials: Credentials) => {
        console.log("Credentials updated:", newCredentials)
        setCredentials(newCredentials)
    }, [])

    const getCredentialsComponent = () => {
        const props = { 
            onCredentialsChange: handleCredentialsChange, 
            initialValues: editingDestination 
        }
        switch (destinationType) {
            case "s3":
                return <DestinationS3Credentials {...props} />
            case "smb":
                return <DestinationSmbCredentials {...props} />
            case "sftp":
                return <DestinationSftpCredentials {...props} />
            case "local_fs":
                return <DestinationFsStoreCredentials {...props} />
            default:
                return null
        }
    }

    const getFilteredDestinations = (type: string) => {
        return destinations.filter(d => d.destination_type === type)
    }

    const handleAddDestination = async () => {
        // Validate credentials
        if (!credentials.url) {
            setNotification({ message: "Please fill in all required credentials", statusCode: 400 })
            return
        }

        setLoading(true)
        setNotification(null)
        try {
            const payload = {
                destination_type: destinationType,
                destination_name: destinationName || undefined,
                credentials: {
                    url: credentials.url,
                    login: credentials.login || null,
                    password: credentials.password || null,
                    api_key: credentials.api_key || null
                }
            }

            console.log("Sending payload:", JSON.stringify(payload, null, 2))

            const response = await post("backup-destinations/add", payload)
            
            if (response.status >= 400) {
                setNotification({ 
                    message: response.detail || "Failed to add backup destination", 
                    statusCode: response.status 
                })
                return
            }

            setNotification({ 
                message: response.message || "Backup destination added successfully", 
                statusCode: response.status 
            })
            
            // Reset form
            setModalOpened(false)
            setDestinationName("")
            setCredentials({
                url: "",
                login: null,
                password: null,
                api_key: null
            })
            setDestinationType("s3")
            setEditingId(null)
            setEditingDestination(null)
            
            await fetchDestinations()
        } catch (err) {
            setNotification({ message: "Failed to add backup destination", statusCode: 500 })
            console.error(err)
        } finally {
            setLoading(false)
        }
    }

    const handleUpdateDestination = async (destinationId: number) => {
        if (!credentials.url) {
            setNotification({ message: "Please fill in required credentials", statusCode: 400 })
            return
        }

        setLoading(true)
        setNotification(null)
        try {
            const payload = {
                destination_id: destinationId,
                destination_name: destinationName || undefined,
                credentials: {
                    url: credentials.url,
                    login: credentials.login || null,
                    password: credentials.password || null,
                    api_key: credentials.api_key || null
                }
            }

            console.log("Updating with payload:", JSON.stringify(payload, null, 2))

            const response = await post("backup-destinations/update", payload)
            
            if (response.status >= 400) {
                setNotification({ 
                    message: response.detail || "Failed to update backup destination", 
                    statusCode: response.status 
                })
                return
            }

            setNotification({ 
                message: response.message || "Backup destination updated successfully", 
                statusCode: response.status 
            })
            
            // Reset form
            setModalOpened(false)
            setEditingId(null)
            setEditingDestination(null)
            setDestinationName("")
            setCredentials({
                url: "",
                login: null,
                password: null,
                api_key: null
            })
            
            await fetchDestinations()
        } catch (err) {
            setNotification({ message: "Failed to update backup destination", statusCode: 500 })
            console.error(err)
        } finally {
            setLoading(false)
        }
    }

    const handleDeleteDestination = async (destinationId: number) => {
        if (!window.confirm("Are you sure you want to delete this backup destination?")) return

        setNotification(null)
        try {
            const response = await del(`backup-destinations/delete?destination_id=${destinationId}`)
            
            if (response.status >= 400) {
                setNotification({ 
                    message: response.detail || "Failed to delete backup destination", 
                    statusCode: response.status 
                })
                return
            }

            setNotification({ 
                message: response.message || "Backup destination deleted successfully", 
                statusCode: response.status 
            })
            await fetchDestinations()
        } catch (err) {
            setNotification({ message: "Failed to delete backup destination", statusCode: 500 })
            console.error(err)
        }
    }

    const handleTestConnection = async (destinationId: number) => {
        setNotification(null)
        try {
            const response = await get(`backup-destinations/test-connection?destination_id=${destinationId}`)
            
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
        setEditingDestination(null)
        setDestinationName("")
        setCredentials({
            url: "",
            login: null,
            password: null,
            api_key: null
        })
        setDestinationType(activeTab || "s3")
        setModalOpened(true)
    }

    const openEditModal = (destination: BackupDestination) => {
        setEditingId(destination.id)
        setEditingDestination(destination)
        setDestinationName(destination.name)
        setDestinationType(destination.destination_type)
        // Credentials will be populated by the credential component's useEffect
        setCredentials({
            url: "",
            login: null,
            password: null,
            api_key: null
        })
        setModalOpened(true)
    }

    const isFormValid = credentials.url

    const DestinationTable = ({ destinations }: { destinations: BackupDestination[] }) => (
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
                {destinations.length === 0 ? (
                    <Table.Tr>
                        <Table.Td colSpan={4} style={{ textAlign: "center", color: "#999" }}>
                            No destinations configured
                        </Table.Td>
                    </Table.Tr>
                ) : (
                    destinations.map((destination) => (
                        <Table.Tr key={destination.id}>
                            <Table.Td>{destination.name}</Table.Td>
                            <Table.Td style={{ fontSize: 12 }}>{destination.url}</Table.Td>
                            <Table.Td style={{ fontSize: 12 }}>
                                {new Date(destination.created_at).toLocaleDateString()}
                            </Table.Td>
                            <Table.Td>
                                <Group gap={8}>
                                    <ActionIcon 
                                        size="sm"
                                        variant="default"
                                        onClick={() => handleTestConnection(destination.id)}
                                        title="Test Connection"
                                    >
                                        <IconCheck size={16} />
                                    </ActionIcon>
                                    <ActionIcon 
                                        size="sm"
                                        variant="default"
                                        onClick={() => openEditModal(destination)}
                                        title="Edit Destination"
                                    >
                                        <IconEdit size={16} />
                                    </ActionIcon>
                                    <ActionIcon 
                                        color="red" 
                                        variant="subtle"
                                        onClick={() => handleDeleteDestination(destination.id)}
                                        title="Delete Destination"
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
                <h1>Backup Destinations</h1>
                <Button 
                    leftSection={<IconPlus size={16} />}
                    onClick={openAddModal}
                >
                    Add Destination
                </Button>
                <ActionIcon 
                    onClick={fetchDestinations} 
                    loading={loadingDestinations} 
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

            {loadingDestinations ? (
                <Loader />
            ) : (
                <Tabs value={activeTab} onChange={setActiveTab}>
                    <Tabs.List>
                        <Tabs.Tab value="s3" leftSection={<IconCloudUpload size={14} />}>
                            S3 ({getFilteredDestinations("s3").length})
                        </Tabs.Tab>
                        <Tabs.Tab value="smb" leftSection={<IconNetwork size={14} />}>
                            SMB ({getFilteredDestinations("smb").length})
                        </Tabs.Tab>
                        <Tabs.Tab value="sftp" leftSection={<IconServer size={14} />}>
                            SFTP ({getFilteredDestinations("sftp").length})
                        </Tabs.Tab>
                        <Tabs.Tab value="local_fs" leftSection={<IconFolder size={14} />}>
                            Local FS ({getFilteredDestinations("local_fs").length})
                        </Tabs.Tab>
                    </Tabs.List>

                    <Tabs.Panel value="s3" pt="md">
                        <DestinationTable destinations={getFilteredDestinations("s3")} />
                    </Tabs.Panel>
                    <Tabs.Panel value="smb" pt="md">
                        <DestinationTable destinations={getFilteredDestinations("smb")} />
                    </Tabs.Panel>
                    <Tabs.Panel value="sftp" pt="md">
                        <DestinationTable destinations={getFilteredDestinations("sftp")} />
                    </Tabs.Panel>
                    <Tabs.Panel value="local_fs" pt="md">
                        <DestinationTable destinations={getFilteredDestinations("local_fs")} />
                    </Tabs.Panel>
                </Tabs>
            )}

            <Modal 
                opened={modalOpened} 
                onClose={() => {
                    setModalOpened(false)
                    setEditingId(null)
                    setEditingDestination(null)
                }}
                title={editingId ? "Edit Backup Destination" : "Add Backup Destination"}
                size="lg"
            >
                <Stack>
                    {!editingId && (
                        <Select
                            data={DESTINATION_TYPES}
                            searchable
                            value={destinationType}
                            label="Destination Type"
                            onChange={(value) => setDestinationType(value || "s3")}
                            required
                        />
                    )}

                    <TextInput
                        label="Destination Name (Optional)"
                        value={destinationName}
                        onChange={(e) => setDestinationName(e.currentTarget.value)}
                        placeholder="e.g., S3 Production Backup"
                    />

                    {getCredentialsComponent()}

                    <Group mt={20}>
                        <Button
                            onClick={() => editingId ? handleUpdateDestination(editingId) : handleAddDestination()}
                            disabled={!isFormValid}
                            loading={loading}
                        >
                            {editingId ? "Update" : "Add"} Destination
                        </Button>
                        <Button 
                            variant="default" 
                            onClick={() => {
                                setModalOpened(false)
                                setEditingId(null)
                                setEditingDestination(null)
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