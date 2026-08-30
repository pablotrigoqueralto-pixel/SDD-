import i18next from 'i18next';
import { initReactI18next } from 'react-i18next';

import accounts from './es-ES/accounts.json';
import activities from './es-ES/activities.json';
import admin from './es-ES/admin.json';
import auth from './es-ES/auth.json';
import catalogue from './es-ES/catalogue.json';
import common from './es-ES/common.json';
import contacts from './es-ES/contacts.json';
import errors from './es-ES/errors.json';
import opportunities from './es-ES/opportunities.json';
import quotes from './es-ES/quotes.json';
import reference from './es-ES/reference.json';

export const DEFAULT_LOCALE = 'es-ES';
export const NAMESPACES = [
  'common',
  'auth',
  'admin',
  'errors',
  'reference',
  'accounts',
  'contacts',
  'activities',
  'catalogue',
  'opportunities',
  'quotes',
] as const;

export const resources = {
  [DEFAULT_LOCALE]: {
    common,
    auth,
    admin,
    errors,
    reference,
    accounts,
    contacts,
    activities,
    catalogue,
    opportunities,
    quotes,
  },
} as const;

export const i18n = i18next;

void i18n.use(initReactI18next).init({
  resources,
  lng: DEFAULT_LOCALE,
  fallbackLng: DEFAULT_LOCALE,
  ns: NAMESPACES,
  defaultNS: 'common',
  returnNull: false,
  interpolation: { escapeValue: false },
  saveMissing: import.meta.env.DEV,
  missingKeyHandler: (_lngs, ns, key) => {
    if (import.meta.env.DEV) {
      console.warn(`[i18n] missing key ${ns}:${key}`);
    }
  },
});

export type Resources = (typeof resources)[typeof DEFAULT_LOCALE];
