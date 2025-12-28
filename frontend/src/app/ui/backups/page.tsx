"use client";

import { useState, useEffect } from "react";
import { BackupFileManager } from "@/components/BackupManager/component";
import { Stack } from "@mantine/core";

export default function BackupsDashboard() {

  return (
    <Stack>
      <BackupFileManager/>
    </Stack>
  );
}
