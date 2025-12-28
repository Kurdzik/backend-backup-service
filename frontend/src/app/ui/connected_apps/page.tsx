"use client";

import { useState, useEffect } from "react";
import { Button, Stack } from "@mantine/core";
import { BackupSourcesManager } from "@/components/BackupSource/component";


export default function ConnectedApps() {

  return (
    <Stack>
      <BackupSourcesManager/>
    </Stack>
  );
}
