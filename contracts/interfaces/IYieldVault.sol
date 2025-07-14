// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

import "@openzeppelin/contracts/interfaces/IERC4626.sol";

/**
 * @title IYieldVault
 * @dev Interface for AI-driven yield farming vaults
 * Extends ERC-4626 with additional yield optimization features
 */
interface IYieldVault is IERC4626 {
    // Events
    event StrategyUpdated(address indexed oldStrategy, address indexed newStrategy);
    event Rebalanced(uint256 totalAssets, uint256 newAllocation);
    event EmergencyPaused(address indexed caller, string reason);
    event EmergencyUnpaused(address indexed caller);
    event YieldHarvested(uint256 amount, uint256 timestamp);
    event RiskProfileUpdated(RiskProfile oldProfile, RiskProfile newProfile);

    // Enums
    enum RiskProfile {
        CONSERVATIVE,
        MODERATE,
        AGGRESSIVE
    }

    enum VaultStatus {
        ACTIVE,
        PAUSED,
        EMERGENCY_PAUSE,
        DEPRECATED
    }

    // Structs
    struct VaultInfo {
        string name;
        string symbol;
        address asset;
        RiskProfile riskProfile;
        VaultStatus status;
        uint256 totalAssets;
        uint256 totalShares;
        uint256 lastRebalance;
        uint256 performanceFee;
        uint256 managementFee;
    }

    struct StrategyAllocation {
        address strategy;
        uint256 allocation; // Percentage in basis points (10000 = 100%)
        uint256 assets;
        bool active;
    }

    // View functions
    function getVaultInfo() external view returns (VaultInfo memory);
    function getRiskProfile() external view returns (RiskProfile);
    function getStatus() external view returns (VaultStatus);
    function getStrategies() external view returns (StrategyAllocation[] memory);
    function getStrategy(address strategy) external view returns (StrategyAllocation memory);
    function getTotalYieldGenerated() external view returns (uint256);
    function getAPY() external view returns (uint256);
    function getLastRebalanceTime() external view returns (uint256);
    function canRebalance() external view returns (bool);
    function getPerformanceMetrics() external view returns (
        uint256 totalReturn,
        uint256 annualizedReturn,
        uint256 sharpeRatio,
        uint256 maxDrawdown
    );

    // Strategy management
    function addStrategy(address strategy, uint256 allocation) external;
    function removeStrategy(address strategy) external;
    function updateStrategyAllocation(address strategy, uint256 newAllocation) external;
    function rebalance() external;
    function harvestYield() external;

    // Risk management
    function setRiskProfile(RiskProfile newProfile) external;
    function emergencyPause(string calldata reason) external;
    function emergencyUnpause() external;
    function emergencyWithdraw(address to) external;

    // Fee management
    function setPerformanceFee(uint256 newFee) external;
    function setManagementFee(uint256 newFee) external;
    function collectFees() external;

    // Access control
    function hasRole(bytes32 role, address account) external view returns (bool);
    function grantRole(bytes32 role, address account) external;
    function revokeRole(bytes32 role, address account) external;
}
