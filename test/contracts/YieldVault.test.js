const { expect } = require("chai");
const { ethers } = require("hardhat");
const { loadFixture } = require("@nomicfoundation/hardhat-network-helpers");

describe("YieldVault", function () {
  // Fixture for deploying contracts
  async function deployYieldVaultFixture() {
    const [owner, user1, user2, feeRecipient] = await ethers.getSigners();

    // Deploy mock ERC20 token
    const MockERC20 = await ethers.getContractFactory("MockERC20");
    const asset = await MockERC20.deploy("Test Token", "TEST", 18);

    // Deploy CircuitBreaker
    const CircuitBreaker = await ethers.getContractFactory("CircuitBreaker");
    const circuitBreaker = await CircuitBreaker.deploy();

    // Deploy YieldVault
    const YieldVault = await ethers.getContractFactory("YieldVault");
    const vault = await YieldVault.deploy(
      asset.address,
      "Test Yield Vault",
      "TYV",
      0, // Conservative risk profile
      owner.address,
      feeRecipient.address
    );

    // Mint tokens to users
    await asset.mint(user1.address, ethers.utils.parseEther("1000"));
    await asset.mint(user2.address, ethers.utils.parseEther("1000"));

    return { vault, asset, owner, user1, user2, feeRecipient };
  }

  describe("Deployment", function () {
    it("Should set the correct asset", async function () {
      const { vault, asset } = await loadFixture(deployYieldVaultFixture);
      expect(await vault.asset()).to.equal(asset.address);
    });

    it("Should set the correct name and symbol", async function () {
      const { vault } = await loadFixture(deployYieldVaultFixture);
      expect(await vault.name()).to.equal("Test Yield Vault");
      expect(await vault.symbol()).to.equal("TYV");
    });

    it("Should set the correct admin roles", async function () {
      const { vault, owner } = await loadFixture(deployYieldVaultFixture);
      const DEFAULT_ADMIN_ROLE = await vault.DEFAULT_ADMIN_ROLE();
      expect(await vault.hasRole(DEFAULT_ADMIN_ROLE, owner.address)).to.be.true;
    });
  });

  describe("Deposits", function () {
    it("Should allow users to deposit assets", async function () {
      const { vault, asset, user1 } = await loadFixture(deployYieldVaultFixture);
      
      const depositAmount = ethers.utils.parseEther("100");
      
      // Approve vault to spend tokens
      await asset.connect(user1).approve(vault.address, depositAmount);
      
      // Deposit
      await expect(vault.connect(user1).deposit(depositAmount, user1.address))
        .to.emit(vault, "Deposit")
        .withArgs(user1.address, user1.address, depositAmount, depositAmount);
      
      // Check balances
      expect(await vault.balanceOf(user1.address)).to.equal(depositAmount);
      expect(await vault.totalAssets()).to.equal(depositAmount);
    });

    it("Should mint correct amount of shares", async function () {
      const { vault, asset, user1 } = await loadFixture(deployYieldVaultFixture);
      
      const depositAmount = ethers.utils.parseEther("100");
      
      await asset.connect(user1).approve(vault.address, depositAmount);
      await vault.connect(user1).deposit(depositAmount, user1.address);
      
      // First deposit should mint 1:1 shares
      expect(await vault.balanceOf(user1.address)).to.equal(depositAmount);
    });

    it("Should revert on zero deposit", async function () {
      const { vault, user1 } = await loadFixture(deployYieldVaultFixture);
      
      await expect(vault.connect(user1).deposit(0, user1.address))
        .to.be.revertedWith("Cannot deposit 0");
    });

    it("Should handle multiple deposits correctly", async function () {
      const { vault, asset, user1, user2 } = await loadFixture(deployYieldVaultFixture);
      
      const deposit1 = ethers.utils.parseEther("100");
      const deposit2 = ethers.utils.parseEther("200");
      
      // First deposit
      await asset.connect(user1).approve(vault.address, deposit1);
      await vault.connect(user1).deposit(deposit1, user1.address);
      
      // Second deposit
      await asset.connect(user2).approve(vault.address, deposit2);
      await vault.connect(user2).deposit(deposit2, user2.address);
      
      expect(await vault.totalAssets()).to.equal(deposit1.add(deposit2));
      expect(await vault.balanceOf(user1.address)).to.equal(deposit1);
      expect(await vault.balanceOf(user2.address)).to.equal(deposit2);
    });
  });

  describe("Withdrawals", function () {
    it("Should allow users to withdraw assets", async function () {
      const { vault, asset, user1 } = await loadFixture(deployYieldVaultFixture);
      
      const depositAmount = ethers.utils.parseEther("100");
      const withdrawAmount = ethers.utils.parseEther("50");
      
      // Deposit first
      await asset.connect(user1).approve(vault.address, depositAmount);
      await vault.connect(user1).deposit(depositAmount, user1.address);
      
      // Withdraw
      const initialBalance = await asset.balanceOf(user1.address);
      await vault.connect(user1).withdraw(withdrawAmount, user1.address, user1.address);
      
      expect(await asset.balanceOf(user1.address)).to.equal(initialBalance.add(withdrawAmount));
      expect(await vault.balanceOf(user1.address)).to.equal(depositAmount.sub(withdrawAmount));
    });

    it("Should revert on zero withdrawal", async function () {
      const { vault, user1 } = await loadFixture(deployYieldVaultFixture);
      
      await expect(vault.connect(user1).withdraw(0, user1.address, user1.address))
        .to.be.revertedWith("Cannot withdraw 0");
    });

    it("Should revert on insufficient balance", async function () {
      const { vault, user1 } = await loadFixture(deployYieldVaultFixture);
      
      const withdrawAmount = ethers.utils.parseEther("100");
      
      await expect(vault.connect(user1).withdraw(withdrawAmount, user1.address, user1.address))
        .to.be.reverted;
    });
  });

  describe("Strategy Management", function () {
    it("Should allow admin to add strategies", async function () {
      const { vault, owner } = await loadFixture(deployYieldVaultFixture);
      
      // Deploy mock strategy
      const MockStrategy = await ethers.getContractFactory("MockStrategy");
      const strategy = await MockStrategy.deploy();
      
      await expect(vault.connect(owner).addStrategy(strategy.address, 5000)) // 50% allocation
        .to.emit(vault, "StrategyUpdated")
        .withArgs(ethers.constants.AddressZero, strategy.address);
      
      const strategies = await vault.getStrategies();
      expect(strategies.length).to.equal(1);
      expect(strategies[0].strategy).to.equal(strategy.address);
      expect(strategies[0].allocation).to.equal(5000);
    });

    it("Should prevent non-admin from adding strategies", async function () {
      const { vault, user1 } = await loadFixture(deployYieldVaultFixture);
      
      const MockStrategy = await ethers.getContractFactory("MockStrategy");
      const strategy = await MockStrategy.deploy();
      
      await expect(vault.connect(user1).addStrategy(strategy.address, 5000))
        .to.be.reverted;
    });

    it("Should prevent total allocation exceeding 100%", async function () {
      const { vault, owner } = await loadFixture(deployYieldVaultFixture);
      
      const MockStrategy = await ethers.getContractFactory("MockStrategy");
      const strategy1 = await MockStrategy.deploy();
      const strategy2 = await MockStrategy.deploy();
      
      // Add first strategy with 60% allocation
      await vault.connect(owner).addStrategy(strategy1.address, 6000);
      
      // Try to add second strategy with 50% allocation (would exceed 100%)
      await expect(vault.connect(owner).addStrategy(strategy2.address, 5000))
        .to.be.revertedWith("Total allocation exceeds 100%");
    });
  });

  describe("Risk Management", function () {
    it("Should allow admin to set risk profile", async function () {
      const { vault, owner } = await loadFixture(deployYieldVaultFixture);
      
      await expect(vault.connect(owner).setRiskProfile(1)) // Moderate
        .to.emit(vault, "RiskProfileUpdated")
        .withArgs(0, 1);
      
      expect(await vault.getRiskProfile()).to.equal(1);
    });

    it("Should allow emergency pause", async function () {
      const { vault, owner } = await loadFixture(deployYieldVaultFixture);
      
      await expect(vault.connect(owner).emergencyPause("Test emergency"))
        .to.emit(vault, "EmergencyPaused")
        .withArgs(owner.address, "Test emergency");
      
      expect(await vault.paused()).to.be.true;
    });

    it("Should prevent deposits when paused", async function () {
      const { vault, asset, owner, user1 } = await loadFixture(deployYieldVaultFixture);
      
      // Pause the vault
      await vault.connect(owner).emergencyPause("Test emergency");
      
      // Try to deposit
      const depositAmount = ethers.utils.parseEther("100");
      await asset.connect(user1).approve(vault.address, depositAmount);
      
      await expect(vault.connect(user1).deposit(depositAmount, user1.address))
        .to.be.revertedWith("Pausable: paused");
    });
  });

  describe("Fee Management", function () {
    it("Should allow admin to set performance fee", async function () {
      const { vault, owner } = await loadFixture(deployYieldVaultFixture);
      
      const newFee = 1500; // 15%
      await vault.connect(owner).setPerformanceFee(newFee);
      
      const vaultInfo = await vault.getVaultInfo();
      expect(vaultInfo.performanceFee).to.equal(newFee);
    });

    it("Should prevent setting fee too high", async function () {
      const { vault, owner } = await loadFixture(deployYieldVaultFixture);
      
      const tooHighFee = 2500; // 25% (max is 20%)
      await expect(vault.connect(owner).setPerformanceFee(tooHighFee))
        .to.be.revertedWith("Fee too high");
    });

    it("Should allow admin to set management fee", async function () {
      const { vault, owner } = await loadFixture(deployYieldVaultFixture);
      
      const newFee = 150; // 1.5%
      await vault.connect(owner).setManagementFee(newFee);
      
      const vaultInfo = await vault.getVaultInfo();
      expect(vaultInfo.managementFee).to.equal(newFee);
    });
  });

  describe("ERC4626 Compliance", function () {
    it("Should implement convertToShares correctly", async function () {
      const { vault } = await loadFixture(deployYieldVaultFixture);
      
      const assets = ethers.utils.parseEther("100");
      const shares = await vault.convertToShares(assets);
      
      // For empty vault, should be 1:1
      expect(shares).to.equal(assets);
    });

    it("Should implement convertToAssets correctly", async function () {
      const { vault } = await loadFixture(deployYieldVaultFixture);
      
      const shares = ethers.utils.parseEther("100");
      const assets = await vault.convertToAssets(shares);
      
      // For empty vault, should be 1:1
      expect(assets).to.equal(shares);
    });

    it("Should implement previewDeposit correctly", async function () {
      const { vault } = await loadFixture(deployYieldVaultFixture);
      
      const assets = ethers.utils.parseEther("100");
      const expectedShares = await vault.previewDeposit(assets);
      const actualShares = await vault.convertToShares(assets);
      
      expect(expectedShares).to.equal(actualShares);
    });

    it("Should implement previewWithdraw correctly", async function () {
      const { vault, asset, user1 } = await loadFixture(deployYieldVaultFixture);
      
      // First deposit some assets
      const depositAmount = ethers.utils.parseEther("100");
      await asset.connect(user1).approve(vault.address, depositAmount);
      await vault.connect(user1).deposit(depositAmount, user1.address);
      
      const withdrawAssets = ethers.utils.parseEther("50");
      const expectedShares = await vault.previewWithdraw(withdrawAssets);
      const actualShares = await vault.convertToShares(withdrawAssets);
      
      expect(expectedShares).to.equal(actualShares);
    });
  });

  describe("Access Control", function () {
    it("Should grant correct roles on deployment", async function () {
      const { vault, owner } = await loadFixture(deployYieldVaultFixture);
      
      const DEFAULT_ADMIN_ROLE = await vault.DEFAULT_ADMIN_ROLE();
      const MANAGER_ROLE = await vault.MANAGER_ROLE();
      const EMERGENCY_ROLE = await vault.EMERGENCY_ROLE();
      
      expect(await vault.hasRole(DEFAULT_ADMIN_ROLE, owner.address)).to.be.true;
      expect(await vault.hasRole(MANAGER_ROLE, owner.address)).to.be.true;
      expect(await vault.hasRole(EMERGENCY_ROLE, owner.address)).to.be.true;
    });

    it("Should allow role granting and revoking", async function () {
      const { vault, owner, user1 } = await loadFixture(deployYieldVaultFixture);
      
      const MANAGER_ROLE = await vault.MANAGER_ROLE();
      
      // Grant role
      await vault.connect(owner).grantRole(MANAGER_ROLE, user1.address);
      expect(await vault.hasRole(MANAGER_ROLE, user1.address)).to.be.true;
      
      // Revoke role
      await vault.connect(owner).revokeRole(MANAGER_ROLE, user1.address);
      expect(await vault.hasRole(MANAGER_ROLE, user1.address)).to.be.false;
    });
  });

  describe("Integration Tests", function () {
    it("Should handle complete deposit-rebalance-withdraw cycle", async function () {
      const { vault, asset, owner, user1 } = await loadFixture(deployYieldVaultFixture);
      
      // Deploy and add mock strategy
      const MockStrategy = await ethers.getContractFactory("MockStrategy");
      const strategy = await MockStrategy.deploy();
      await vault.connect(owner).addStrategy(strategy.address, 5000); // 50%
      
      // User deposits
      const depositAmount = ethers.utils.parseEther("100");
      await asset.connect(user1).approve(vault.address, depositAmount);
      await vault.connect(user1).deposit(depositAmount, user1.address);
      
      // Rebalance (would normally be called by keeper)
      // Note: This would require a more sophisticated mock strategy
      
      // User withdraws
      const withdrawAmount = ethers.utils.parseEther("50");
      await vault.connect(user1).withdraw(withdrawAmount, user1.address, user1.address);
      
      expect(await vault.balanceOf(user1.address)).to.equal(depositAmount.sub(withdrawAmount));
    });
  });
});
