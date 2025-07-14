import React, { useState, useEffect } from 'react';
import {
  Box,
  Grid,
  Card,
  CardContent,
  Typography,
  Button,
  Chip,
  LinearProgress,
  IconButton,
  Tooltip,
} from '@mui/material';
import {
  TrendingUp,
  AccountBalance,
  Security,
  Speed,
  Refresh,
  Add,
  Warning,
  CheckCircle,
} from '@mui/icons-material';
import { motion } from 'framer-motion';

// Components
import MetricCard from '../components/dashboard/MetricCard';
import PortfolioChart from '../components/dashboard/PortfolioChart';
import RecentTransactions from '../components/dashboard/RecentTransactions';
import TopStrategies from '../components/dashboard/TopStrategies';
import RiskOverview from '../components/dashboard/RiskOverview';
import QuickActions from '../components/dashboard/QuickActions';

// Hooks
import { useWeb3 } from '../hooks/useWeb3';
import { useApi } from '../hooks/useApi';
import { useWebSocket } from '../hooks/useWebSocket';

// Types
interface DashboardData {
  totalValue: number;
  totalReturn: number;
  apy: number;
  riskScore: number;
  activeVaults: number;
  pendingTransactions: number;
}

interface PortfolioAllocation {
  protocol: string;
  allocation: number;
  value: number;
  apy: number;
  risk: number;
}

const Dashboard: React.FC = () => {
  const { account, isConnected } = useWeb3();
  const { get } = useApi();
  const [dashboardData, setDashboardData] = useState<DashboardData | null>(null);
  const [portfolioData, setPortfolioData] = useState<PortfolioAllocation[]>([]);
  const [loading, setLoading] = useState(true);
  const [lastUpdate, setLastUpdate] = useState<Date>(new Date());

  // WebSocket for real-time updates
  const { data: realtimeData } = useWebSocket('/ws/dashboard', {
    enabled: isConnected && !!account,
  });

  // Fetch dashboard data
  const fetchDashboardData = async () => {
    if (!isConnected || !account) return;

    try {
      setLoading(true);
      
      // Fetch user portfolio summary
      const [summaryResponse, portfolioResponse] = await Promise.all([
        get(`/api/v1/users/${account}/summary`),
        get(`/api/v1/users/${account}/portfolio`),
      ]);

      setDashboardData(summaryResponse.data);
      setPortfolioData(portfolioResponse.data.allocations || []);
      setLastUpdate(new Date());
    } catch (error) {
      console.error('Failed to fetch dashboard data:', error);
    } finally {
      setLoading(false);
    }
  };

  // Initial data fetch
  useEffect(() => {
    fetchDashboardData();
  }, [account, isConnected]);

  // Update with real-time data
  useEffect(() => {
    if (realtimeData) {
      setDashboardData(prev => ({
        ...prev,
        ...realtimeData,
      }));
    }
  }, [realtimeData]);

  // Auto-refresh every 30 seconds
  useEffect(() => {
    const interval = setInterval(() => {
      fetchDashboardData();
    }, 30000);

    return () => clearInterval(interval);
  }, [account, isConnected]);

  if (!isConnected) {
    return (
      <Box
        display="flex"
        justifyContent="center"
        alignItems="center"
        minHeight="60vh"
        flexDirection="column"
      >
        <Typography variant="h4" gutterBottom>
          Connect Your Wallet
        </Typography>
        <Typography variant="body1" color="text.secondary" mb={3}>
          Connect your wallet to start optimizing your DeFi yields with AI
        </Typography>
        <Button variant="contained" size="large">
          Connect Wallet
        </Button>
      </Box>
    );
  }

  if (loading && !dashboardData) {
    return (
      <Box>
        <Typography variant="h4" gutterBottom>
          Dashboard
        </Typography>
        <LinearProgress sx={{ mb: 3 }} />
        <Grid container spacing={3}>
          {[1, 2, 3, 4].map((i) => (
            <Grid item xs={12} sm={6} md={3} key={i}>
              <Card>
                <CardContent>
                  <Box height={100} />
                </CardContent>
              </Card>
            </Grid>
          ))}
        </Grid>
      </Box>
    );
  }

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(value);
  };

  const formatPercentage = (value: number) => {
    return `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`;
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
    >
      <Box>
        {/* Header */}
        <Box
          display="flex"
          justifyContent="space-between"
          alignItems="center"
          mb={3}
        >
          <Box>
            <Typography variant="h4" gutterBottom>
              Dashboard
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Last updated: {lastUpdate.toLocaleTimeString()}
            </Typography>
          </Box>
          <Box display="flex" gap={1}>
            <Tooltip title="Refresh Data">
              <IconButton onClick={fetchDashboardData} disabled={loading}>
                <Refresh />
              </IconButton>
            </Tooltip>
            <Button
              variant="contained"
              startIcon={<Add />}
              href="/vaults"
            >
              New Vault
            </Button>
          </Box>
        </Box>

        {/* Metrics Cards */}
        <Grid container spacing={3} mb={3}>
          <Grid item xs={12} sm={6} md={3}>
            <MetricCard
              title="Total Portfolio Value"
              value={formatCurrency(dashboardData?.totalValue || 0)}
              change={dashboardData?.totalReturn || 0}
              icon={<AccountBalance />}
              color="primary"
            />
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <MetricCard
              title="Average APY"
              value={formatPercentage(dashboardData?.apy || 0)}
              change={2.3}
              icon={<TrendingUp />}
              color="success"
            />
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <MetricCard
              title="Risk Score"
              value={`${dashboardData?.riskScore || 0}/100`}
              change={-1.2}
              icon={<Security />}
              color={
                (dashboardData?.riskScore || 0) < 30
                  ? 'success'
                  : (dashboardData?.riskScore || 0) < 70
                  ? 'warning'
                  : 'error'
              }
            />
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <MetricCard
              title="Active Vaults"
              value={dashboardData?.activeVaults || 0}
              icon={<Speed />}
              color="info"
            />
          </Grid>
        </Grid>

        {/* Main Content */}
        <Grid container spacing={3}>
          {/* Portfolio Chart */}
          <Grid item xs={12} lg={8}>
            <Card>
              <CardContent>
                <Box
                  display="flex"
                  justifyContent="space-between"
                  alignItems="center"
                  mb={2}
                >
                  <Typography variant="h6">Portfolio Performance</Typography>
                  <Box display="flex" gap={1}>
                    <Chip label="7D" size="small" />
                    <Chip label="30D" size="small" variant="outlined" />
                    <Chip label="90D" size="small" variant="outlined" />
                  </Box>
                </Box>
                <PortfolioChart data={portfolioData} />
              </CardContent>
            </Card>
          </Grid>

          {/* Quick Actions */}
          <Grid item xs={12} lg={4}>
            <QuickActions />
          </Grid>

          {/* Risk Overview */}
          <Grid item xs={12} md={6}>
            <RiskOverview riskScore={dashboardData?.riskScore || 0} />
          </Grid>

          {/* Top Strategies */}
          <Grid item xs={12} md={6}>
            <TopStrategies strategies={portfolioData} />
          </Grid>

          {/* Recent Transactions */}
          <Grid item xs={12}>
            <RecentTransactions />
          </Grid>
        </Grid>

        {/* Status Indicators */}
        <Box
          position="fixed"
          bottom={20}
          right={20}
          display="flex"
          flexDirection="column"
          gap={1}
        >
          {dashboardData?.pendingTransactions && dashboardData.pendingTransactions > 0 && (
            <Chip
              icon={<Warning />}
              label={`${dashboardData.pendingTransactions} pending`}
              color="warning"
              size="small"
            />
          )}
          <Chip
            icon={<CheckCircle />}
            label="System Healthy"
            color="success"
            size="small"
          />
        </Box>
      </Box>
    </motion.div>
  );
};

export default Dashboard;
