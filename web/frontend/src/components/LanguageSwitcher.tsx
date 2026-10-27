import { useTranslation } from "react-i18next"
import { Languages } from "lucide-react"
import { Select, SelectContent, SelectItem, SelectTrigger } from "@/components/ui/select"
import { LANGUAGES } from "@/i18n"

export function LanguageSwitcher({ className }: { className?: string }) {
  const { i18n } = useTranslation()

  return (
    <Select value={i18n.resolvedLanguage} onValueChange={(code) => i18n.changeLanguage(code)}>
      <SelectTrigger size="sm" className={className} aria-label="Language" title="Language">
        <Languages className="h-4 w-4" />
      </SelectTrigger>
      {/* sem SelectValue no gatilho o modo "item-aligned" não tem onde se ancorar; abre para cima, alinhado ao botão */}
      <SelectContent position="popper" side="top" align="start" className="p-1.5">
        {LANGUAGES.map((lang) => (
          <SelectItem key={lang.code} value={lang.code} className="py-1.5 pl-2">
            {lang.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}
