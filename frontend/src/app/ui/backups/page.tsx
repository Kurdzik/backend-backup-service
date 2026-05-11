"use client";

import { BackupFileManager } from "@/components/BackupManager/component";
import { Stack } from "@mantine/core";

export default function BackupsDashboard() {

  return (
    <Stack>
      <BackupFileManager/>
    </Stack>
  );
}
