"use client";

import { useState, useEffect, useMemo } from "react";
import { post, get } from "@/lib/backendRequests";

export default function ConnectedApps() {

    useMemo(()=>{
        get("users/get-info").then(res=>
            {console.log(res.data)
            console.log(res.data.tenant_id)
            }
        )
    },[])

    return (
        <></>
    );
}
