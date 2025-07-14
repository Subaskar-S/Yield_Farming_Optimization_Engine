// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

/**
 * @title IStrategy
 * @dev Interface for yield farming strategies
 */
interface IStrategy {
    // Events
    event Deposited(uint256 amount, uint256 timestamp);
    event Withdrawn(uint256 amount, uint256 timestamp);
    event YieldHarvested(uint256 amount, uint256 timestamp);
    event EmergencyExited(uint256 recoveredAmount);

    // Enums
    enum StrategyStatus {
        ACTIVE,
        PAUSED,
        DEPRECATED,
        EMERGENCY
    }

    // Structs
    struct StrategyInfo {
        string name;
        string protocol;
        address asset;
        StrategyStatus status;
        uint256 totalDeposited;
        uint256 totalYieldGenerated;
        uint256 lastHarvest;
        uint256 riskScore; // 0-100, higher = riskier
        uint256 expectedAPY; // In basis points
    }

    struct PerformanceMetrics {
        uint256 totalReturn;
        uint256 annualizedReturn;
        uint256 volatility;
        uint256 sharpeRatio;
        uint256 maxDrawdown;
        uint256 winRate;
    }

    // View functions
    function getStrategyInfo() external view returns (StrategyInfo memory);
    function getPerformanceMetrics() external view returns (PerformanceMetrics memory);
    function getAsset() external view returns (address);
    function getVault() external view returns (address);
    function balanceOf() external view returns (uint256);
    function balanceOfWant() external view returns (uint256);
    function balanceOfPool() external view returns (uint256);
    function estimatedTotalAssets() external view returns (uint256);
    function isActive() external view returns (bool);
    function canHarvest() external view returns (bool);
    function expectedReturn() external view returns (uint256);
    function getRiskScore() external view returns (uint256);

    // Core functions
    function deposit(uint256 amount) external;
    function withdraw(uint256 amount) external returns (uint256);
    function withdrawAll() external returns (uint256);
    function harvest() external returns (uint256);
    function emergencyExit() external returns (uint256);

    // Strategy management
    function setVault(address vault) external;
    function pause() external;
    function unpause() external;
    function retire() external;

    // Risk management
    function setMaxSlippage(uint256 slippage) external;
    function setMinHarvestAmount(uint256 amount) external;
    function updateRiskScore(uint256 newScore) external;

    // Protocol-specific functions (to be implemented by each strategy)
    function getProtocolInfo() external view returns (
        string memory protocolName,
        string memory version,
        address protocolAddress
    );
    
    function getRewards() external view returns (address[] memory tokens, uint256[] memory amounts);
    function claimRewards() external;
}
