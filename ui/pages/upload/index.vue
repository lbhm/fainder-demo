# mock uploadpage

<template>
  <v-main>
    <v-divider />
    <div class="d-flex align-center justify-center flex-column">
      <h1 class="mt-16">Upload Page</h1>
      <p>
        Upload new Croissant files with dataset profiles to the search engine.
      </p>
      <v-form class="mt-4" @submit.prevent="handleSubmit">
        <v-file-input
          v-model="files"
          label="Select Files"
          multiple
          prepend-icon="mdi-file"
          class="mb-4"
          accept=".json"
          width="40rem"
          :rules="[
            (v) =>
              !v ||
              v.every((file: any) => file?.type === 'application/json') ||
              'Only JSON files are allowed',
          ]"
        />
        <div class="d-flex justify-end">
          <v-btn
            prepend-icon="mdi-upload"
            type="submit"
            color="primary"
            :loading="isUploading"
            :disabled="!files || files.length === 0"
          >
            Upload Dataset
          </v-btn>
        </div>
      </v-form>

      <v-alert
        v-if="alert"
        :type="alert.type"
        :text="alert.message"
        class="mt-4"
      />
    </div>
  </v-main>
</template>

<script setup lang="ts">
import {ref, type Ref} from "vue";

interface Alert {
  type: "success" | "error";
  message: string;
}

const files: Ref<File[] | null> = ref(null);
const isUploading: Ref<boolean> = ref(false);
const alert: Ref<Alert | null> = ref(null);

const handleSubmit = async (): Promise<void> => {
  if (!files.value) return;

  isUploading.value = true;
  alert.value = null;

  try {
    const formData = new FormData();
    files.value.forEach((file: File) => {
      formData.append("files", file);
    });

    const response = await fetch("http://localhost:8000/upload", {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
      throw new Error(await response.text());
    }

    alert.value = {
      type: "success",
      message: "Files uploaded successfully",
    };
    files.value = null;
  } catch (error: any) {
    alert.value = {
      type: "error",
      message: `Upload failed: ${error.message}`,
    };
  } finally {
    isUploading.value = false;
  }
};
</script>
