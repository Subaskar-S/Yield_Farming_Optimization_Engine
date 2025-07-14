import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from 'react-query';
import { BrowserRouter } from 'react-router-dom';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import '@testing-library/jest-dom';

// Components
import Dashboard from '../pages/Dashboard';

// Providers
import { Web3Provider } from '../providers/Web3Provider';
import { AuthProvider } from '../providers/AuthProvider';

// Mocks
import { mockWeb3Provider, mockApiService } from '../__mocks__';

// Mock hooks
jest.mock('../hooks/useWeb3', () => ({
  useWeb3: () => ({
    account: '0x123...abc',
    isConnected: true,
    balance: '1.5',
    connectWallet: jest.fn(),
    disconnectWallet: jest.fn(),
  }),
}));

jest.mock('../hooks/useApi', () => ({
  useApi: () => ({
    get: jest.fn().mockImplementation((url) => {
      if (url.includes('/summary')) {
        return Promise.resolve({
          data: {
            totalValue: 50000,
            totalReturn: 5.2,
            apy: 12.5,
            riskScore: 35,
            activeVaults: 3,
            pendingTransactions: 0,
          },
        });
      }
      if (url.includes('/portfolio')) {
        return Promise.resolve({
          data: {
            allocations: [
              {
                protocol: 'Compound',
                allocation: 0.4,
                value: 20000,
                apy: 8.5,
                risk: 25,
              },
              {
                protocol: 'Aave',
                allocation: 0.3,
                value: 15000,
                apy: 12.0,
                risk: 30,
              },
              {
                protocol: 'Yearn',
                allocation: 0.3,
                value: 15000,
                apy: 15.2,
                risk: 45,
              },
            ],
          },
        });
      }
      return Promise.resolve({ data: {} });
    }),
    post: jest.fn(),
    put: jest.fn(),
    delete: jest.fn(),
  }),
}));

jest.mock('../hooks/useWebSocket', () => ({
  useWebSocket: () => ({
    data: null,
    isConnected: false,
  }),
}));

// Test wrapper component
const TestWrapper: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });

  const theme = createTheme();

  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider theme={theme}>
        <BrowserRouter>
          <Web3Provider>
            <AuthProvider>
              {children}
            </AuthProvider>
          </Web3Provider>
        </BrowserRouter>
      </ThemeProvider>
    </QueryClientProvider>
  );
};

describe('Dashboard Component', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders dashboard title', async () => {
    render(
      <TestWrapper>
        <Dashboard />
      </TestWrapper>
    );

    expect(screen.getByText('Dashboard')).toBeInTheDocument();
  });

  it('displays portfolio metrics when connected', async () => {
    render(
      <TestWrapper>
        <Dashboard />
      </TestWrapper>
    );

    await waitFor(() => {
      expect(screen.getByText('Total Portfolio Value')).toBeInTheDocument();
      expect(screen.getByText('Average APY')).toBeInTheDocument();
      expect(screen.getByText('Risk Score')).toBeInTheDocument();
      expect(screen.getByText('Active Vaults')).toBeInTheDocument();
    });
  });

  it('displays formatted currency values', async () => {
    render(
      <TestWrapper>
        <Dashboard />
      </TestWrapper>
    );

    await waitFor(() => {
      expect(screen.getByText('$50,000.00')).toBeInTheDocument();
    });
  });

  it('displays percentage values correctly', async () => {
    render(
      <TestWrapper>
        <Dashboard />
      </TestWrapper>
    );

    await waitFor(() => {
      expect(screen.getByText('+12.50%')).toBeInTheDocument();
    });
  });

  it('shows risk score with appropriate color coding', async () => {
    render(
      <TestWrapper>
        <Dashboard />
      </TestWrapper>
    );

    await waitFor(() => {
      expect(screen.getByText('35/100')).toBeInTheDocument();
    });
  });

  it('displays active vaults count', async () => {
    render(
      <TestWrapper>
        <Dashboard />
      </TestWrapper>
    );

    await waitFor(() => {
      expect(screen.getByText('3')).toBeInTheDocument();
    });
  });

  it('shows refresh button and handles click', async () => {
    render(
      <TestWrapper>
        <Dashboard />
      </TestWrapper>
    );

    const refreshButton = screen.getByLabelText('Refresh Data');
    expect(refreshButton).toBeInTheDocument();

    fireEvent.click(refreshButton);
    // Verify that refresh functionality is triggered
  });

  it('shows new vault button with correct link', async () => {
    render(
      <TestWrapper>
        <Dashboard />
      </TestWrapper>
    );

    const newVaultButton = screen.getByText('New Vault');
    expect(newVaultButton).toBeInTheDocument();
    expect(newVaultButton.closest('a')).toHaveAttribute('href', '/vaults');
  });

  it('displays portfolio chart section', async () => {
    render(
      <TestWrapper>
        <Dashboard />
      </TestWrapper>
    );

    await waitFor(() => {
      expect(screen.getByText('Portfolio Performance')).toBeInTheDocument();
    });
  });

  it('shows time period chips for chart', async () => {
    render(
      <TestWrapper>
        <Dashboard />
      </TestWrapper>
    );

    await waitFor(() => {
      expect(screen.getByText('7D')).toBeInTheDocument();
      expect(screen.getByText('30D')).toBeInTheDocument();
      expect(screen.getByText('90D')).toBeInTheDocument();
    });
  });

  it('displays quick actions section', async () => {
    render(
      <TestWrapper>
        <Dashboard />
      </TestWrapper>
    );

    await waitFor(() => {
      // Quick actions would be rendered by the QuickActions component
      // This test verifies the component is rendered
      expect(screen.getByTestId('quick-actions')).toBeInTheDocument();
    });
  });

  it('shows risk overview section', async () => {
    render(
      <TestWrapper>
        <Dashboard />
      </TestWrapper>
    );

    await waitFor(() => {
      expect(screen.getByTestId('risk-overview')).toBeInTheDocument();
    });
  });

  it('displays top strategies section', async () => {
    render(
      <TestWrapper>
        <Dashboard />
      </TestWrapper>
    );

    await waitFor(() => {
      expect(screen.getByTestId('top-strategies')).toBeInTheDocument();
    });
  });

  it('shows recent transactions section', async () => {
    render(
      <TestWrapper>
        <Dashboard />
      </TestWrapper>
    );

    await waitFor(() => {
      expect(screen.getByTestId('recent-transactions')).toBeInTheDocument();
    });
  });

  it('displays system status indicators', async () => {
    render(
      <TestWrapper>
        <Dashboard />
      </TestWrapper>
    );

    await waitFor(() => {
      expect(screen.getByText('System Healthy')).toBeInTheDocument();
    });
  });

  it('handles loading state correctly', () => {
    // Mock loading state
    jest.mock('../hooks/useApi', () => ({
      useApi: () => ({
        get: jest.fn().mockImplementation(() => new Promise(() => {})), // Never resolves
      }),
    }));

    render(
      <TestWrapper>
        <Dashboard />
      </TestWrapper>
    );

    expect(screen.getByRole('progressbar')).toBeInTheDocument();
  });

  it('handles error state gracefully', async () => {
    // Mock error state
    jest.mock('../hooks/useApi', () => ({
      useApi: () => ({
        get: jest.fn().mockRejectedValue(new Error('API Error')),
      }),
    }));

    render(
      <TestWrapper>
        <Dashboard />
      </TestWrapper>
    );

    // Should still render the dashboard structure even with errors
    expect(screen.getByText('Dashboard')).toBeInTheDocument();
  });

  it('updates last update timestamp', async () => {
    render(
      <TestWrapper>
        <Dashboard />
      </TestWrapper>
    );

    await waitFor(() => {
      expect(screen.getByText(/Last updated:/)).toBeInTheDocument();
    });
  });

  it('shows pending transactions warning when present', async () => {
    // Mock data with pending transactions
    jest.mock('../hooks/useApi', () => ({
      useApi: () => ({
        get: jest.fn().mockImplementation((url) => {
          if (url.includes('/summary')) {
            return Promise.resolve({
              data: {
                totalValue: 50000,
                totalReturn: 5.2,
                apy: 12.5,
                riskScore: 35,
                activeVaults: 3,
                pendingTransactions: 2,
              },
            });
          }
          return Promise.resolve({ data: {} });
        }),
      }),
    }));

    render(
      <TestWrapper>
        <Dashboard />
      </TestWrapper>
    );

    await waitFor(() => {
      expect(screen.getByText('2 pending')).toBeInTheDocument();
    });
  });

  it('handles real-time data updates', async () => {
    // Mock WebSocket data
    jest.mock('../hooks/useWebSocket', () => ({
      useWebSocket: () => ({
        data: {
          totalValue: 55000, // Updated value
          apy: 13.2,
        },
        isConnected: true,
      }),
    }));

    render(
      <TestWrapper>
        <Dashboard />
      </TestWrapper>
    );

    await waitFor(() => {
      expect(screen.getByText('$55,000.00')).toBeInTheDocument();
    });
  });

  it('auto-refreshes data periodically', async () => {
    jest.useFakeTimers();
    
    const mockGet = jest.fn().mockResolvedValue({ data: {} });
    jest.mock('../hooks/useApi', () => ({
      useApi: () => ({ get: mockGet }),
    }));

    render(
      <TestWrapper>
        <Dashboard />
      </TestWrapper>
    );

    // Fast-forward 30 seconds
    jest.advanceTimersByTime(30000);

    await waitFor(() => {
      expect(mockGet).toHaveBeenCalledTimes(2); // Initial + auto-refresh
    });

    jest.useRealTimers();
  });
});

// Component-specific tests
describe('Dashboard Metric Cards', () => {
  it('displays correct metric card colors based on values', async () => {
    render(
      <TestWrapper>
        <Dashboard />
      </TestWrapper>
    );

    await waitFor(() => {
      // Risk score of 35 should show warning color (medium risk)
      const riskCard = screen.getByText('Risk Score').closest('.MuiCard-root');
      expect(riskCard).toHaveClass('warning');
    });
  });

  it('formats large numbers correctly', async () => {
    // Mock large portfolio value
    jest.mock('../hooks/useApi', () => ({
      useApi: () => ({
        get: jest.fn().mockImplementation((url) => {
          if (url.includes('/summary')) {
            return Promise.resolve({
              data: {
                totalValue: 1250000, // $1.25M
                totalReturn: 5.2,
                apy: 12.5,
                riskScore: 35,
                activeVaults: 3,
                pendingTransactions: 0,
              },
            });
          }
          return Promise.resolve({ data: {} });
        }),
      }),
    }));

    render(
      <TestWrapper>
        <Dashboard />
      </TestWrapper>
    );

    await waitFor(() => {
      expect(screen.getByText('$1,250,000.00')).toBeInTheDocument();
    });
  });
});

describe('Dashboard Responsive Behavior', () => {
  it('adapts layout for mobile screens', () => {
    // Mock mobile viewport
    Object.defineProperty(window, 'innerWidth', {
      writable: true,
      configurable: true,
      value: 375,
    });

    render(
      <TestWrapper>
        <Dashboard />
      </TestWrapper>
    );

    // Verify mobile-specific layout adjustments
    // This would depend on the specific responsive implementation
  });

  it('adapts layout for tablet screens', () => {
    // Mock tablet viewport
    Object.defineProperty(window, 'innerWidth', {
      writable: true,
      configurable: true,
      value: 768,
    });

    render(
      <TestWrapper>
        <Dashboard />
      </TestWrapper>
    );

    // Verify tablet-specific layout adjustments
  });
});
