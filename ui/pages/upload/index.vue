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
              v.every((file) => file?.type === 'application/json') ||
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

<script setup>
const files = ref(null);
const isUploading = ref(false);
const alert = ref(null);

const handleSubmit = async () => {
  if (!files.value) return;

  isUploading.value = true;
  alert.value = null;

  try {
    const formData = new FormData();
    files.value.forEach((file) => {
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
  } catch (error) {
    alert.value = {
      type: "error",
      message: `Upload failed: ${error.message}`,
    };
  } finally {
    isUploading.value = false;
  }
};
</script>
