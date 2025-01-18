<template>
  <v-app>
    <v-app-bar rounded>
      <Logo size="medium" class="mr-4" @click="gotoHome"/>
      <v-spacer></v-spacer>

      <v-menu>
        <template v-slot:activator="{ props }">
          <v-btn icon v-bind="props">
            <v-icon>mdi-menu</v-icon>
          </v-btn>
        </template>

        <v-list>
          <v-list-item @click="navigateTo('/upload')">
            <template v-slot:prepend>
              <v-icon icon="mdi-upload"></v-icon>
            </template>
            <v-list-item-title>Upload Datasets</v-list-item-title>
          </v-list-item>

          <v-list-item @click="navigateTo('/about')">
            <template v-slot:prepend>
              <v-icon icon="mdi-information"></v-icon>
            </template>
            <v-list-item-title>About</v-list-item-title>
          </v-list-item>

          <v-divider></v-divider>

          <v-list-item @click="toggleHighlight">
            <template v-slot:prepend>
              <v-icon icon="mdi-marker"></v-icon>
            </template>
            <v-list-item-title>
              {{ highlightEnabled ? 'Disable Syntax Highlight' : 'Enable Syntax Highlight' }}
            </v-list-item-title>
          </v-list-item>

          <v-list-item @click="toggleTheme">
            <template v-slot:prepend>
              <v-icon :icon="theme.global.current.value.dark ? 'mdi-weather-sunny' : 'mdi-weather-night'"
                     :color="theme.global.current.value.dark ? 'yellow' : 'indigo'">
              </v-icon>
            </template>
            <v-list-item-title>
              {{ theme.global.current.value.dark ? 'Light Mode' : 'Dark Mode' }}
            </v-list-item-title>
          </v-list-item>
        </v-list>
      </v-menu>
    </v-app-bar>
    <NuxtLayout>
      <NuxtPage />
    </NuxtLayout>
  </v-app>
</template>

<script setup>
  import { useTheme } from 'vuetify'
  import { useRoute } from 'vue-router'
  import Logo from '~/components/Logo.vue'

  function gotoHome() {
    console.log('go to home')
    return navigateTo({path:'/'})
  }

  const route = useRoute();
  const theme = useTheme();
  const colorMode = useColorMode();
  const highlightEnabled = useCookie('highlight-enabled', { default: () => true })

  let currentTheme = route.query.theme || colorMode.value;
  theme.global.name.value = currentTheme === "dark" ? "dark" : "light";

  function toggleTheme() {
    theme.global.name.value = theme.global.name.value === 'dark' ? "light" : "dark";


    navigateTo({
      path: route.path,
      query: {
        ...route.query,
        theme: theme.global.name.value
      }
    });

  }

  function toggleHighlight() {
    highlightEnabled.value = !highlightEnabled.value
  }
</script>
