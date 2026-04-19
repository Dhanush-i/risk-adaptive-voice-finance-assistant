import { useState } from 'react';

/**
 * Contacts List — 10 dummy contacts for the demo.
 * 
 * Contact names match the names used in the intent dataset
 * so that voice commands like "Send 500 to Rahul" will resolve correctly.
 */

const CONTACTS = [
  { id: 1, name: 'Rahul Sharma',   upi: 'rahul@okaxis',   phone: '9876543210' },
  { id: 2, name: 'Priya Patel',    upi: 'priya@oksbi',    phone: '9876543211' },
  { id: 3, name: 'Amit Kumar',     upi: 'amit@okicici',   phone: '9876543212' },
  { id: 4, name: 'Sneha Gupta',    upi: 'sneha@okhdfc',   phone: '9876543213' },
  { id: 5, name: 'Vikram Singh',   upi: 'vikram@okaxis',  phone: '9876543214' },
  { id: 6, name: 'Ananya Rao',     upi: 'ananya@oksbi',   phone: '9876543215' },
  { id: 7, name: 'Rohan Verma',    upi: 'rohan@okicici',  phone: '9876543216' },
  { id: 8, name: 'Deepa Nair',     upi: 'deepa@okhdfc',   phone: '9876543217' },
  { id: 9, name: 'Arjun Das',      upi: 'arjun@okaxis',   phone: '9876543218' },
  { id: 10, name: 'Kavya Menon',   upi: 'kavya@oksbi',    phone: '9876543219' },
  { id: 11, name: 'Dhanush I',     upi: 'dhanush@okaxis', phone: '9876543220' },
  { id: 12, name: 'Jahnavi Reddy', upi: 'jahnavi@oksbi',  phone: '9876543221' },
  { id: 13, name: 'Ravi Teja',     upi: 'ravi@okicici',   phone: '9876543222' },
  { id: 14, name: 'Kundan Roy',    upi: 'kundan@okhdfc',  phone: '9876543223' },
  { id: 15, name: 'Jathin Sai',    upi: 'jathin@okaxis',  phone: '9876543224' },
  { id: 16, name: 'Balaram Reddy', upi: 'balaram@oksbi',  phone: '9876543225' },
];

const AVATAR_COLORS = [
  '#8B5CF6', '#6366F1', '#EC4899', '#14B8A6', '#F59E0B',
  '#EF4444', '#3B82F6', '#10B981', '#F97316', '#8B5CF6',
  '#7C3AED', '#0EA5E9', '#D946EF', '#22C55E', '#E11D48', '#06B6D4',
];

export default function ContactsList() {
  const [search, setSearch] = useState('');

  const filtered = CONTACTS.filter(
    (c) =>
      c.name.toLowerCase().includes(search.toLowerCase()) ||
      c.upi.toLowerCase().includes(search.toLowerCase()) ||
      c.phone.includes(search)
  );

  const getInitials = (name) => {
    const parts = name.split(' ');
    return parts.length >= 2
      ? (parts[0][0] + parts[1][0]).toUpperCase()
      : name.substring(0, 2).toUpperCase();
  };

  return (
    <div className="contacts-page">
      <div className="contacts-header">
        <h2 className="section-title">Saved Contacts</h2>
        <p className="section-subtitle">
          Say a contact's first name in your voice command — e.g. "Send 500 to <strong>Rahul</strong>"
        </p>
      </div>

      <div className="contacts-search">
        <input
          type="text"
          placeholder="Search by name, UPI, or phone..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="contacts-search-input"
          id="contacts-search"
        />
      </div>

      <div className="contacts-grid">
        {filtered.map((contact, i) => (
          <div key={contact.id} className="contact-card animate-in" style={{ animationDelay: `${i * 0.04}s` }}>
            <div
              className="contact-avatar"
              style={{ backgroundColor: AVATAR_COLORS[(contact.id - 1) % AVATAR_COLORS.length] }}
            >
              {getInitials(contact.name)}
            </div>
            <div className="contact-info">
              <div className="contact-name">{contact.name}</div>
              <div className="contact-upi">{contact.upi}</div>
              <div className="contact-phone">{contact.phone}</div>
            </div>
          </div>
        ))}
      </div>

      {filtered.length === 0 && (
        <div className="empty-state">
          <div className="empty-state-icon">🔍</div>
          <p>No contacts found matching "{search}"</p>
        </div>
      )}
    </div>
  );
}
