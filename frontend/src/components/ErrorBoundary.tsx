import React from 'react';

interface Props {
  children: React.ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export default class ErrorBoundary extends React.Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error('ErrorBoundary capturó un error:', error, info);
  }

  handleReload = () => {
    this.setState({ hasError: false, error: null });
    window.location.reload();
  };

  render() {
    if (this.state.hasError) {
      return (
        <div
          className="min-h-screen flex items-center justify-center p-6"
          style={{ backgroundColor: 'var(--bg-page)' }}
        >
          <div
            className="max-w-md w-full rounded-lg p-6 text-center"
            style={{ backgroundColor: 'var(--bg-card)', border: '1px solid var(--border)' }}
          >
            <div className="text-lg font-semibold" style={{ color: 'var(--text-primary)' }}>
              Ocurrió un error inesperado
            </div>
            <div className="text-sm mt-2" style={{ color: 'var(--text-muted)' }}>
              La aplicación encontró un problema y no pudo continuar. Podés recargar la página para reintentar.
            </div>
            {this.state.error?.message && (
              <div
                className="text-xs mt-3 p-2 rounded text-left overflow-auto"
                style={{ backgroundColor: 'var(--bg-page)', color: 'var(--text-muted)' }}
              >
                {this.state.error.message}
              </div>
            )}
            <button
              onClick={this.handleReload}
              className="mt-4 px-4 py-2 rounded text-sm font-medium"
              style={{ backgroundColor: 'var(--accent)', color: 'var(--text-on-accent)' }}
            >
              Recargar
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
