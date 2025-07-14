import React, { useState, useEffect } from 'react';
import {
  Box,
  Grid,
  Card,
  CardContent,
  Typography,
  Button,
  Chip,
  TextField,
  InputAdornment,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Fab,
  Tooltip,
} from '@mui/material';
import {
  Search,
  FilterList,
  Add,
  TrendingUp,
  Security,
  AccountBalance,
  Launch,
} from '@mui/icons-material';
import { motion, AnimatePresence } from 'framer-motion';

// Components
import VaultCard from '../components/vaults/VaultCard';
import CreateVaultDialog from '../components/vaults/CreateVaultDialog';
import VaultFilters from '../components/vaults/VaultFilters';

// Hooks
import { useWeb3 } from '../hooks/useWeb3';
import { useApi } from '../hooks/useApi';

// Types
interface Vault {
  id: string;
  name: string;
  symbol: string;
  asset: string;
  totalAssets: number;
  totalSupply: number;
  apy: number;
  riskProfile: 'conservative' | 'moderate' | 'aggressive';
  riskScore: number;
  status: 'active' | 'paused' | 'deprecated';
  userBalance: number;
  userShares: number;
  strategies: string[];
  lastRebalance: string;
  performanceMetrics: {
    totalReturn: number;
    sharpeRatio: number;
    maxDrawdown: number;
  };
}

interface VaultFilters {
  search: string;
  riskProfile: string;
  minApy: number;
  maxRisk: number;
  status: string;
  sortBy: string;
  sortOrder: 'asc' | 'desc';
}

const Vaults: React.FC = () => {
  const { account, isConnected } = useWeb3();
  const { get } = useApi();
  
  const [vaults, setVaults] = useState<Vault[]>([]);
  const [filteredVaults, setFilteredVaults] = useState<Vault[]>([]);
  const [loading, setLoading] = useState(true);
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [filtersOpen, setFiltersOpen] = useState(false);
  
  const [filters, setFilters] = useState<VaultFilters>({
    search: '',
    riskProfile: '',
    minApy: 0,
    maxRisk: 100,
    status: '',
    sortBy: 'apy',
    sortOrder: 'desc',
  });

  // Fetch vaults data
  const fetchVaults = async () => {
    try {
      setLoading(true);
      const response = await get('/api/v1/vaults');
      setVaults(response.data);
    } catch (error) {
      console.error('Failed to fetch vaults:', error);
    } finally {
      setLoading(false);
    }
  };

  // Filter and sort vaults
  useEffect(() => {
    let filtered = [...vaults];

    // Apply search filter
    if (filters.search) {
      filtered = filtered.filter(vault =>
        vault.name.toLowerCase().includes(filters.search.toLowerCase()) ||
        vault.symbol.toLowerCase().includes(filters.search.toLowerCase()) ||
        vault.asset.toLowerCase().includes(filters.search.toLowerCase())
      );
    }

    // Apply risk profile filter
    if (filters.riskProfile) {
      filtered = filtered.filter(vault => vault.riskProfile === filters.riskProfile);
    }

    // Apply APY filter
    if (filters.minApy > 0) {
      filtered = filtered.filter(vault => vault.apy >= filters.minApy);
    }

    // Apply risk score filter
    if (filters.maxRisk < 100) {
      filtered = filtered.filter(vault => vault.riskScore <= filters.maxRisk);
    }

    // Apply status filter
    if (filters.status) {
      filtered = filtered.filter(vault => vault.status === filters.status);
    }

    // Apply sorting
    filtered.sort((a, b) => {
      let aValue: any = a[filters.sortBy as keyof Vault];
      let bValue: any = b[filters.sortBy as keyof Vault];

      if (typeof aValue === 'string') {
        aValue = aValue.toLowerCase();
        bValue = bValue.toLowerCase();
      }

      if (filters.sortOrder === 'asc') {
        return aValue > bValue ? 1 : -1;
      } else {
        return aValue < bValue ? 1 : -1;
      }
    });

    setFilteredVaults(filtered);
  }, [vaults, filters]);

  // Initial data fetch
  useEffect(() => {
    fetchVaults();
  }, []);

  const handleFilterChange = (newFilters: Partial<VaultFilters>) => {
    setFilters(prev => ({ ...prev, ...newFilters }));
  };

  const handleCreateVault = () => {
    setCreateDialogOpen(true);
  };

  const handleVaultCreated = () => {
    setCreateDialogOpen(false);
    fetchVaults(); // Refresh the list
  };

  const getRiskColor = (riskProfile: string) => {
    switch (riskProfile) {
      case 'conservative':
        return 'success';
      case 'moderate':
        return 'warning';
      case 'aggressive':
        return 'error';
      default:
        return 'default';
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'active':
        return 'success';
      case 'paused':
        return 'warning';
      case 'deprecated':
        return 'error';
      default:
        return 'default';
    }
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
              Yield Vaults
            </Typography>
            <Typography variant="body2" color="text.secondary">
              AI-optimized yield farming strategies
            </Typography>
          </Box>
          <Button
            variant="contained"
            startIcon={<Add />}
            onClick={handleCreateVault}
            disabled={!isConnected}
          >
            Create Vault
          </Button>
        </Box>

        {/* Search and Filters */}
        <Card sx={{ mb: 3 }}>
          <CardContent>
            <Grid container spacing={2} alignItems="center">
              <Grid item xs={12} md={4}>
                <TextField
                  fullWidth
                  placeholder="Search vaults..."
                  value={filters.search}
                  onChange={(e) => handleFilterChange({ search: e.target.value })}
                  InputProps={{
                    startAdornment: (
                      <InputAdornment position="start">
                        <Search />
                      </InputAdornment>
                    ),
                  }}
                />
              </Grid>
              <Grid item xs={12} md={2}>
                <FormControl fullWidth>
                  <InputLabel>Risk Profile</InputLabel>
                  <Select
                    value={filters.riskProfile}
                    label="Risk Profile"
                    onChange={(e) => handleFilterChange({ riskProfile: e.target.value })}
                  >
                    <MenuItem value="">All</MenuItem>
                    <MenuItem value="conservative">Conservative</MenuItem>
                    <MenuItem value="moderate">Moderate</MenuItem>
                    <MenuItem value="aggressive">Aggressive</MenuItem>
                  </Select>
                </FormControl>
              </Grid>
              <Grid item xs={12} md={2}>
                <FormControl fullWidth>
                  <InputLabel>Status</InputLabel>
                  <Select
                    value={filters.status}
                    label="Status"
                    onChange={(e) => handleFilterChange({ status: e.target.value })}
                  >
                    <MenuItem value="">All</MenuItem>
                    <MenuItem value="active">Active</MenuItem>
                    <MenuItem value="paused">Paused</MenuItem>
                    <MenuItem value="deprecated">Deprecated</MenuItem>
                  </Select>
                </FormControl>
              </Grid>
              <Grid item xs={12} md={2}>
                <FormControl fullWidth>
                  <InputLabel>Sort By</InputLabel>
                  <Select
                    value={filters.sortBy}
                    label="Sort By"
                    onChange={(e) => handleFilterChange({ sortBy: e.target.value })}
                  >
                    <MenuItem value="apy">APY</MenuItem>
                    <MenuItem value="totalAssets">TVL</MenuItem>
                    <MenuItem value="riskScore">Risk Score</MenuItem>
                    <MenuItem value="name">Name</MenuItem>
                  </Select>
                </FormControl>
              </Grid>
              <Grid item xs={12} md={2}>
                <Button
                  fullWidth
                  variant="outlined"
                  startIcon={<FilterList />}
                  onClick={() => setFiltersOpen(true)}
                >
                  Advanced
                </Button>
              </Grid>
            </Grid>
          </CardContent>
        </Card>

        {/* Vault Stats */}
        <Grid container spacing={2} mb={3}>
          <Grid item xs={12} sm={4}>
            <Card>
              <CardContent>
                <Box display="flex" alignItems="center" gap={1}>
                  <AccountBalance color="primary" />
                  <Box>
                    <Typography variant="h6">
                      {vaults.length}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      Total Vaults
                    </Typography>
                  </Box>
                </Box>
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={12} sm={4}>
            <Card>
              <CardContent>
                <Box display="flex" alignItems="center" gap={1}>
                  <TrendingUp color="success" />
                  <Box>
                    <Typography variant="h6">
                      {vaults.length > 0 
                        ? (vaults.reduce((sum, v) => sum + v.apy, 0) / vaults.length).toFixed(2)
                        : '0.00'
                      }%
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      Average APY
                    </Typography>
                  </Box>
                </Box>
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={12} sm={4}>
            <Card>
              <CardContent>
                <Box display="flex" alignItems="center" gap={1}>
                  <Security color="warning" />
                  <Box>
                    <Typography variant="h6">
                      {vaults.length > 0 
                        ? Math.round(vaults.reduce((sum, v) => sum + v.riskScore, 0) / vaults.length)
                        : '0'
                      }
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      Average Risk
                    </Typography>
                  </Box>
                </Box>
              </CardContent>
            </Card>
          </Grid>
        </Grid>

        {/* Vaults Grid */}
        {loading ? (
          <Grid container spacing={3}>
            {[1, 2, 3, 4, 5, 6].map((i) => (
              <Grid item xs={12} sm={6} md={4} key={i}>
                <Card>
                  <CardContent>
                    <Box height={200} />
                  </CardContent>
                </Card>
              </Grid>
            ))}
          </Grid>
        ) : (
          <AnimatePresence>
            <Grid container spacing={3}>
              {filteredVaults.map((vault, index) => (
                <Grid item xs={12} sm={6} md={4} key={vault.id}>
                  <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -20 }}
                    transition={{ duration: 0.3, delay: index * 0.1 }}
                  >
                    <VaultCard vault={vault} />
                  </motion.div>
                </Grid>
              ))}
            </Grid>
          </AnimatePresence>
        )}

        {/* Empty State */}
        {!loading && filteredVaults.length === 0 && (
          <Box
            display="flex"
            flexDirection="column"
            alignItems="center"
            justifyContent="center"
            minHeight="40vh"
          >
            <Typography variant="h6" gutterBottom>
              No vaults found
            </Typography>
            <Typography variant="body2" color="text.secondary" mb={2}>
              {vaults.length === 0 
                ? "Create your first vault to start earning optimized yields"
                : "Try adjusting your filters to see more results"
              }
            </Typography>
            {vaults.length === 0 && (
              <Button
                variant="contained"
                startIcon={<Add />}
                onClick={handleCreateVault}
                disabled={!isConnected}
              >
                Create Your First Vault
              </Button>
            )}
          </Box>
        )}

        {/* Floating Action Button */}
        <Tooltip title="Create New Vault">
          <Fab
            color="primary"
            sx={{
              position: 'fixed',
              bottom: 20,
              right: 20,
            }}
            onClick={handleCreateVault}
            disabled={!isConnected}
          >
            <Add />
          </Fab>
        </Tooltip>

        {/* Create Vault Dialog */}
        <CreateVaultDialog
          open={createDialogOpen}
          onClose={() => setCreateDialogOpen(false)}
          onVaultCreated={handleVaultCreated}
        />

        {/* Advanced Filters Dialog */}
        <VaultFilters
          open={filtersOpen}
          onClose={() => setFiltersOpen(false)}
          filters={filters}
          onFiltersChange={handleFilterChange}
        />
      </Box>
    </motion.div>
  );
};

export default Vaults;
