import React from 'react';
import { Globe } from 'lucide-react';
import { Button } from '../components/ui/button';
import { t } from '../i18n';

export const LanguageSwitcher = () => {
  // Get current language from localStorage or default to 'en'
  const currentLang = localStorage.getItem('lang') || 'en';

  const handleLanguageChange = (lang: string) => {
    localStorage.setItem('lang', lang);
    window.location.reload(); // Reload to apply language change
  };

  return (
    <div className="relative group">
      <Button 
        variant="ghost" 
        size="sm" 
        className="gap-2"
        onClick={() => handleLanguageChange(currentLang === 'en' ? 'ru' : 'en')}
      >
        <Globe className="h-4 w-4" />
        {currentLang.toUpperCase()}
      </Button>
    </div>
  );
}; 