import { useTranslation } from 'react-i18next'

export default function ListaAmbientes() {
  const { t } = useTranslation()
  return <h1 className="p-8 text-2xl font-bold">{t('placeholders.environmentList')}</h1>
}