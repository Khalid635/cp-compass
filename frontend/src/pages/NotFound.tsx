import { Link } from 'react-router-dom';
import { Compass } from 'lucide-react';
import { useLanguage } from '../i18n';
import { Button } from '../components/ui';

export default function NotFound() {
  const { t } = useLanguage();
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-3 px-4 text-center">
      <Compass size={40} className="text-muted" aria-hidden />
      <h1 className="text-2xl font-semibold tracking-tight">{t.notFoundTitle}</h1>
      <p className="text-sm text-muted">{t.notFoundText}</p>
      <Link to="/">
        <Button>{t.goHome}</Button>
      </Link>
    </div>
  );
}
