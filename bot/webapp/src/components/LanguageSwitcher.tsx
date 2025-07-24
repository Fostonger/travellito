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

  return null;
}; 