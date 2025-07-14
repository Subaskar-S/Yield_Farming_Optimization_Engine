import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import { CssBaseline, Box } from '@mui/material';
import { QueryClient, QueryClientProvider } from 'react-query';
import { Toaster } from 'react-hot-toast';

// Components
import Navbar from './components/layout/Navbar';
import Sidebar from './components/layout/Sidebar';
import Footer from './components/layout/Footer';

// Pages
import Dashboard from './pages/Dashboard';
import Vaults from './pages/Vaults';
import VaultDetail from './pages/VaultDetail';
import Strategies from './pages/Strategies';
import Analytics from './pages/Analytics';
import RiskManagement from './pages/RiskManagement';
import Settings from './pages/Settings';

// Providers
import { Web3Provider } from './providers/Web3Provider';
import { AuthProvider } from './providers/AuthProvider';

// Hooks
import { useThemeMode } from './hooks/useThemeMode';

// Create React Query client
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
      staleTime: 5 * 60 * 1000, // 5 minutes
    },
  },
});

function App() {
  const { themeMode, toggleTheme } = useThemeMode();

  // Create theme
  const theme = createTheme({
    palette: {
      mode: themeMode,
      primary: {
        main: '#2196f3',
        light: '#64b5f6',
        dark: '#1976d2',
      },
      secondary: {
        main: '#ff9800',
        light: '#ffb74d',
        dark: '#f57c00',
      },
      background: {
        default: themeMode === 'dark' ? '#0a0e27' : '#f5f5f5',
        paper: themeMode === 'dark' ? '#1a1d3a' : '#ffffff',
      },
      success: {
        main: '#4caf50',
      },
      warning: {
        main: '#ff9800',
      },
      error: {
        main: '#f44336',
      },
    },
    typography: {
      fontFamily: '"Inter", "Roboto", "Helvetica", "Arial", sans-serif',
      h1: {
        fontSize: '2.5rem',
        fontWeight: 600,
      },
      h2: {
        fontSize: '2rem',
        fontWeight: 600,
      },
      h3: {
        fontSize: '1.75rem',
        fontWeight: 600,
      },
      h4: {
        fontSize: '1.5rem',
        fontWeight: 600,
      },
      h5: {
        fontSize: '1.25rem',
        fontWeight: 600,
      },
      h6: {
        fontSize: '1rem',
        fontWeight: 600,
      },
    },
    components: {
      MuiButton: {
        styleOverrides: {
          root: {
            textTransform: 'none',
            borderRadius: 8,
            fontWeight: 600,
          },
        },
      },
      MuiCard: {
        styleOverrides: {
          root: {
            borderRadius: 12,
            boxShadow: themeMode === 'dark' 
              ? '0 4px 20px rgba(0, 0, 0, 0.3)'
              : '0 4px 20px rgba(0, 0, 0, 0.1)',
          },
        },
      },
      MuiPaper: {
        styleOverrides: {
          root: {
            borderRadius: 12,
          },
        },
      },
    },
  });

  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider theme={theme}>
        <CssBaseline />
        <Web3Provider>
          <AuthProvider>
            <Router>
              <Box sx={{ display: 'flex', minHeight: '100vh' }}>
                {/* Sidebar */}
                <Sidebar />
                
                {/* Main Content */}
                <Box
                  component="main"
                  sx={{
                    flexGrow: 1,
                    display: 'flex',
                    flexDirection: 'column',
                    minHeight: '100vh',
                  }}
                >
                  {/* Navbar */}
                  <Navbar onToggleTheme={toggleTheme} />
                  
                  {/* Page Content */}
                  <Box
                    sx={{
                      flexGrow: 1,
                      p: 3,
                      backgroundColor: 'background.default',
                    }}
                  >
                    <Routes>
                      <Route path="/" element={<Dashboard />} />
                      <Route path="/dashboard" element={<Dashboard />} />
                      <Route path="/vaults" element={<Vaults />} />
                      <Route path="/vaults/:id" element={<VaultDetail />} />
                      <Route path="/strategies" element={<Strategies />} />
                      <Route path="/analytics" element={<Analytics />} />
                      <Route path="/risk" element={<RiskManagement />} />
                      <Route path="/settings" element={<Settings />} />
                    </Routes>
                  </Box>
                  
                  {/* Footer */}
                  <Footer />
                </Box>
              </Box>
            </Router>
            
            {/* Toast Notifications */}
            <Toaster
              position="top-right"
              toastOptions={{
                duration: 4000,
                style: {
                  background: theme.palette.background.paper,
                  color: theme.palette.text.primary,
                  border: `1px solid ${theme.palette.divider}`,
                },
                success: {
                  iconTheme: {
                    primary: theme.palette.success.main,
                    secondary: theme.palette.success.contrastText,
                  },
                },
                error: {
                  iconTheme: {
                    primary: theme.palette.error.main,
                    secondary: theme.palette.error.contrastText,
                  },
                },
              }}
            />
          </AuthProvider>
        </Web3Provider>
      </ThemeProvider>
    </QueryClientProvider>
  );
}

export default App;
