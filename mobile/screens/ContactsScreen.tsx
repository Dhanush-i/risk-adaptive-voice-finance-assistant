import React, { useState, useEffect } from 'react';
import {
  View, Text, FlatList, TouchableOpacity, StyleSheet, TextInput,
} from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { COLORS } from '../constants/theme';

const DEFAULT_CONTACTS = [
  { id: '1', name: 'Rahul Sharma', upi: 'rahul@okaxis' },
  { id: '2', name: 'Priya Patel', upi: 'priya@oksbi' },
  { id: '3', name: 'Amit Kumar', upi: 'amit@okicici' },
  { id: '4', name: 'Sneha Gupta', upi: 'sneha@okhdfc' },
  { id: '5', name: 'Vikram Singh', upi: 'vikram@okaxis' },
  { id: '6', name: 'Ananya Rao', upi: 'ananya@oksbi' },
  { id: '7', name: 'Rohan Verma', upi: 'rohan@okicici' },
  { id: '8', name: 'Deepa Nair', upi: 'deepa@okhdfc' },
  { id: '9', name: 'Arjun Das', upi: 'arjun@okaxis' },
  { id: '10', name: 'Kavya Menon', upi: 'kavya@oksbi' },
  { id: '11', name: 'Dhanush I', upi: 'dhanush@okaxis' },
  { id: '12', name: 'Jahnavi Reddy', upi: 'jahnavi@oksbi' },
  { id: '13', name: 'Ravi Teja', upi: 'ravi@okicici' },
  { id: '14', name: 'Kundan Roy', upi: 'kundan@okhdfc' },
  { id: '15', name: 'Jathin Sai', upi: 'jathin@okaxis' },
  { id: '16', name: 'Balaram Reddy', upi: 'balaram@oksbi' },
];

interface Contact {
  id: string;
  name: string;
  upi: string;
}

export default function ContactsScreen() {
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [search, setSearch] = useState('');

  useEffect(() => {
    loadContacts();
  }, []);

  const loadContacts = async () => {
    try {
      const stored = await AsyncStorage.getItem('voicepay_contacts');
      if (stored) {
        setContacts(JSON.parse(stored));
      } else {
        setContacts(DEFAULT_CONTACTS);
        await AsyncStorage.setItem('voicepay_contacts', JSON.stringify(DEFAULT_CONTACTS));
      }
    } catch {
      setContacts(DEFAULT_CONTACTS);
    }
  };

  const filtered = contacts.filter(
    (c) =>
      c.name.toLowerCase().includes(search.toLowerCase()) ||
      c.upi.toLowerCase().includes(search.toLowerCase())
  );

  const getInitials = (name: string) => {
    const parts = name.split(' ');
    return parts.length >= 2
      ? (parts[0][0] + parts[1][0]).toUpperCase()
      : name.substring(0, 2).toUpperCase();
  };

  const avatarColors = ['#8B5CF6', '#6366F1', '#EC4899', '#14B8A6', '#F59E0B', '#EF4444'];

  return (
    <View style={s.container}>
      <TextInput
        style={s.search}
        placeholder="Search contacts..."
        placeholderTextColor={COLORS.textMuted}
        value={search}
        onChangeText={setSearch}
      />
      <FlatList
        data={filtered}
        keyExtractor={(item) => item.id}
        contentContainerStyle={{ paddingBottom: 24 }}
        renderItem={({ item, index }) => (
          <TouchableOpacity style={s.item}>
            <View style={[s.avatar, { backgroundColor: avatarColors[index % avatarColors.length] }]}>
              <Text style={s.avatarText}>{getInitials(item.name)}</Text>
            </View>
            <View style={{ flex: 1 }}>
              <Text style={s.name}>{item.name}</Text>
              <Text style={s.upi}>{item.upi}</Text>
            </View>
          </TouchableOpacity>
        )}
        ListEmptyComponent={
          <Text style={s.empty}>No contacts found</Text>
        }
      />
    </View>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.bgMain, padding: 16 },
  search: {
    backgroundColor: COLORS.bgInput,
    borderWidth: 1,
    borderColor: COLORS.border,
    borderRadius: 12,
    padding: 12,
    color: COLORS.textMain,
    fontSize: 14,
    marginBottom: 16,
  },
  item: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 14,
    padding: 14,
    borderRadius: 14,
    backgroundColor: COLORS.bgCard,
    borderWidth: 1,
    borderColor: COLORS.border,
    marginBottom: 8,
  },
  avatar: {
    width: 44,
    height: 44,
    borderRadius: 22,
    justifyContent: 'center',
    alignItems: 'center',
  },
  avatarText: { color: '#fff', fontWeight: '700', fontSize: 14 },
  name: { fontSize: 15, fontWeight: '600', color: COLORS.textMain },
  upi: { fontSize: 12, color: COLORS.textMuted, marginTop: 2 },
  empty: { textAlign: 'center', color: COLORS.textMuted, marginTop: 40, fontSize: 14 },
});
