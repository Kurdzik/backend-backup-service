"use client"
import { post } from "@/lib/backendRequests"
import { useState } from "react"

interface AddBackupSourceProps {
    source_type: "postgres" | "elasticsearch" | "vault" | "qdrant" 
    source_name?: string
    credentials : {
        url: string
        login?: string
        password?: string
        api_key?: string
    }
}

function formatPostgresCredentials(url: string) {
    const [host, setHost] = useState<string>()
    const [port, setPort] = useState<string>()

    const [username, setUsername] = useState<string>()
    const [password, setPassword] = useState<string>()



    return 
}

export function AddBackupSource() {
    const [sourceType, setSourceType] = useState<"postgres" | "elasticsearch" | "vault" | "qdrant" >("postgres")
    const [sourceName, setSourceName] = useState<string | null>(null)
    const [credentials, setCredentials] = useState<null>()


    return (<>
    
    </>)
}



export function BackupSource() {
    
    
    
    return (<>
    
    </>)
}