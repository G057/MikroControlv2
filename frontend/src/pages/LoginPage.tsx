import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { useTheme } from '../contexts/ThemeContext';
import { Eye, EyeOff, Sun, Moon } from 'lucide-react';
import { logoAPI } from '../services/api';
import toast from 'react-hot-toast';

export default function LoginPage() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const { toggle, isDark, c } = useTheme();
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try { await login(username, password); toast.success('Sesión iniciada'); navigate('/'); }
    catch (err: any) { toast.error(err.message || 'Credenciales incorrectas'); }
    finally { setLoading(false); }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4" style={{ background: c.bgPage, color: c.textPrimary }}>
      <div className="w-full max-w-md">
        <div className="flex justify-end mb-4">
          <button onClick={toggle} className="p-2 rounded-lg" style={{ color: c.textMuted, background: c.bgCard, border: `1px solid ${c.border}` }}
            title={isDark ? 'Modo día' : 'Modo noche'}>
            {isDark ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
          </button>
        </div>
        <div className="text-center mb-8">
          <img src={logoAPI.url()} alt="MikroControl" className="h-14 mx-auto mb-4" />
          <h1 className="text-3xl font-bold" style={{ color: c.textPrimary }}>MikroControl</h1>
          <p className="mt-2" style={{ color: c.textMuted }}>Sistema de gestión MikroTik</p>
        </div>
        <form onSubmit={handleSubmit} className="card space-y-4">
          <div>
            <label className="block text-sm font-semibold mb-1" style={{ color: c.textSecondary }}>Usuario</label>
            <input type="text" className="input" placeholder="admin" value={username} onChange={e => setUsername(e.target.value)} required autoFocus />
          </div>
          <div>
            <label className="block text-sm font-semibold mb-1" style={{ color: c.textSecondary }}>Contraseña</label>
            <div className="relative">
              <input type={showPassword ? 'text' : 'password'} className="input pr-10" placeholder="••••••••" value={password} onChange={e => setPassword(e.target.value)} required />
              <button type="button" className="absolute right-3 top-1/2 -translate-y-1/2" style={{ color: c.textMuted }} onClick={() => setShowPassword(!showPassword)}>
                {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
          </div>
          <button type="submit" className="btn-primary w-full" disabled={loading}>{loading ? 'Ingresando...' : 'Iniciar Sesión'}</button>
        </form>
      </div>
    </div>
  );
}
