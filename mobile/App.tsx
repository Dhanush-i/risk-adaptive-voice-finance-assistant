import React, { useState } from 'react';
import { NavigationContainer, DarkTheme } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { StatusBar } from 'expo-status-bar';
import { COLORS } from './constants/theme';
import LoginScreen from './screens/LoginScreen';
import HomeScreen from './screens/HomeScreen';
import ContactsScreen from './screens/ContactsScreen';
import QRScannerScreen from './screens/QRScannerScreen';
import VoiceEnrollScreen from './screens/VoiceEnrollScreen';

const Stack = createNativeStackNavigator();

const navTheme = {
  ...DarkTheme,
  colors: {
    ...DarkTheme.colors,
    background: COLORS.bgMain,
    card: COLORS.bgSurface,
    text: COLORS.textMain,
    primary: COLORS.primary,
    border: COLORS.border,
    notification: COLORS.primary,
  },
};

export default function App() {
  const [user, setUser] = useState<any>(null);

  return (
    <>
      <StatusBar style="light" />
      <NavigationContainer theme={navTheme}>
        <Stack.Navigator screenOptions={{ headerShown: false }}>
          {!user ? (
            <Stack.Screen name="Login">
              {(props) => <LoginScreen {...props} onLogin={setUser} />}
            </Stack.Screen>
          ) : (
            <>
              <Stack.Screen name="Home">
                {(props) => <HomeScreen {...props} user={user} onLogout={() => setUser(null)} />}
              </Stack.Screen>
              <Stack.Screen
                name="Contacts"
                component={ContactsScreen as any}
                options={{ headerShown: true, title: 'Contacts' }}
              />
              <Stack.Screen
                name="QRScanner"
                component={QRScannerScreen as any}
                options={{ headerShown: false }}
              />
              <Stack.Screen
                name="VoiceEnroll"
                component={VoiceEnrollScreen as any}
                options={{ headerShown: false }}
              />
            </>
          )}
        </Stack.Navigator>
      </NavigationContainer>
    </>
  );
}
