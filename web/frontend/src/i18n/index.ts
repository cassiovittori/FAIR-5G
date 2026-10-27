import i18n from 'i18next'
import LanguageDetector from 'i18next-browser-languagedetector'
import { initReactI18next } from 'react-i18next'
import { ptBR } from './locales/pt-BR'
import { en } from './locales/en'

export const LANGUAGES = [
  { code: 'pt-BR', label: 'Português (BR)' },
  { code: 'en', label: 'English' },
] as const

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources: { 'pt-BR': { translation: ptBR }, en: { translation: en } },
    fallbackLng: 'pt-BR',
    supportedLngs: ['pt-BR', 'en'],
    interpolation: { escapeValue: false },
    detection: {
      order: ['localStorage', 'navigator'],
      lookupLocalStorage: 'fair5g.lang',
      caches: ['localStorage'],
    },
  })

export const currentLocale = () => i18n.resolvedLanguage ?? 'pt-BR'

const syncHtmlLang = () => { document.documentElement.lang = currentLocale() }
i18n.on('languageChanged', syncHtmlLang)
syncHtmlLang()

export default i18n
