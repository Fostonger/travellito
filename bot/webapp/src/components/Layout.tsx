import React, { ReactNode } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Calendar, Home } from 'lucide-react';
import { Button } from '../components/ui/button';
import { t } from '../i18n';
import { LanguageSwitcher } from './LanguageSwitcher';

interface LayoutProps {
  children: ReactNode;
}

export const Layout = ({ children }: LayoutProps) => {
  const location = useLocation();
  const isToursPage = location.pathname === '/tours' || location.pathname === '/';

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="sticky top-0 z-50 border-b bg-card shadow-card">
        <div className="container mx-auto px-4 py-3">
          <div className="flex items-center justify-between">
            <Link to="/tours" className="flex items-center gap-2">
              <div className="h-8 w-8 rounded-lg bg-gradient-to-r from-cyan-700 to-blue-600 flex items-center justify-center">
                <Home className="h-4 w-4 text-white" />
              </div>
              <span className={`font-semibold ${isToursPage ? 'text-primary' : 'text-foreground'}`}>Tours</span>
            </Link>
            
            <div className="flex items-center gap-2">
              <Link to="/bookings" className="gap-2">
                <Button
                  variant={location.pathname === '/bookings' ? 'default' : 'ghost'}
                  size="sm"
                  className="flex items-center gap-2"
                >
                  <Calendar className="h-4 w-4" />
                  {t('my_bookings')}
                </Button>
              </Link>
              <LanguageSwitcher />
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="container mx-auto px-4 py-6">
        {children}
      </main>
    </div>
  );
}; 
