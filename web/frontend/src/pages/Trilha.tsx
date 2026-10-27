import { useTranslation } from 'react-i18next'

export default function Trilha() {
  const { t } = useTranslation()
  return <h1 className="p-8 text-2xl font-bold">{t('placeholders.tutorial')}</h1>
}