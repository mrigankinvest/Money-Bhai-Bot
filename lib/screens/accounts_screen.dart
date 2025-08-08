import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../models/wallet_model.dart';
import '../services/firestore_service.dart';

// --- 1. Convert to StatefulWidget to manage its own state ---
class AccountsScreen extends StatefulWidget {
  // --- 2. Add a Key to allow the parent to access its state ---
  const AccountsScreen({super.key});

  @override
  State<AccountsScreen> createState() => AccountsScreenState();
}

class AccountsScreenState extends State<AccountsScreen> {
  final FirestoreService _firestoreService = FirestoreService();
  List<Wallet> _allWallets = [];
  List<Wallet> _filteredWallets = [];
  List<Wallet> _goalWallets = [];
  String _selectedCategory = 'All';
  bool _isLoading = true;
  double _netWorth = 0.0;

  @override
  void initState() {
    super.initState();
    _fetchWallets();
  }

  // --- 3. Expose the fetch method so the parent (HomeScreen) can call it ---
  Future<void> refreshData() async {
    await _fetchWallets();
  }

  Future<void> _fetchWallets() async {
    if (mounted) setState(() => _isLoading = true);
    _allWallets = await _firestoreService.getWallets();
    _calculateAndSetNetWorth();
    _filterGoalWallets();
    _applyFilter();
    if (mounted) setState(() => _isLoading = false);
  }

  void _calculateAndSetNetWorth() {
    double total = 0.0;
    for (var wallet in _allWallets) {
      if (wallet.category == 'Expense' || wallet.category == 'Investment') {
        total += wallet.balance;
      }
    }
    _netWorth = total;
  }

  void _filterGoalWallets() {
    _goalWallets = _allWallets.where((w) => w.category == 'Goal').toList();
  }

  void _applyFilter() {
    final nonGoalWallets = _allWallets
        .where((w) => w.category != 'Goal')
        .toList();
    if (_selectedCategory == 'All') {
      _filteredWallets = nonGoalWallets;
    } else {
      _filteredWallets = nonGoalWallets
          .where((wallet) => wallet.category == _selectedCategory)
          .toList();
    }
    setState(() {});
  }

  @override
  Widget build(BuildContext context) {
    return DefaultTabController(
      length: 3, // Wallets, Goals, Budgets
      child: Scaffold(
        appBar: _buildCustomAppBar(),
        body: _isLoading
            ? const Center(child: CircularProgressIndicator())
            : TabBarView(
                children: [
                  _buildWalletsTab(),
                  _buildGoalsTab(),
                  _buildBudgetsTab(),
                ],
              ),
        floatingActionButton: FloatingActionButton(
          onPressed: () async {
            final result = await Navigator.pushNamed(context, '/create_wallet');
            if (result == true) _fetchWallets();
          },
          backgroundColor: const Color(0xFF0D256E),
          foregroundColor: Colors.white,
          child: const Icon(Icons.add),
        ),
      ),
    );
  }

  AppBar _buildCustomAppBar() {
    return AppBar(
      backgroundColor: const Color(0xFF0D256E),
      foregroundColor: Colors.white,
      leading: IconButton(icon: const Icon(Icons.menu), onPressed: () {}),
      title: const Text(''), // Title is handled by the tabs
      actions: [
        IconButton(
          icon: const Icon(Icons.notifications_none),
          onPressed: () {},
        ),
        IconButton(icon: const Icon(Icons.bookmark_border), onPressed: () {}),
        IconButton(icon: const Icon(Icons.search), onPressed: () {}),
        IconButton(icon: const Icon(Icons.tune), onPressed: () {}),
      ],
      bottom: const TabBar(
        labelColor: Colors.white,
        unselectedLabelColor: Colors.white70,
        indicatorColor: Colors.redAccent,
        indicatorWeight: 3.0,
        tabs: [
          Tab(text: 'Wallets'),
          Tab(text: 'Goals'),
          Tab(text: 'Budgets'),
        ],
      ),
    );
  }

  Widget _buildWalletsTab() {
    final currencyFormat = NumberFormat.currency(locale: 'en_IN', symbol: '₹');

    return Column(
      children: [
        Container(
          width: double.infinity,
          padding: const EdgeInsets.all(16),
          color: Colors.grey[200],
          child: Column(
            children: [
              const Text(
                'Net Worth',
                style: TextStyle(fontSize: 16, color: Colors.grey),
              ),
              const SizedBox(height: 4),
              Text(
                currencyFormat.format(_netWorth),
                style: const TextStyle(
                  fontSize: 24,
                  fontWeight: FontWeight.bold,
                  color: Color(0xFF0D256E),
                ),
              ),
            ],
          ),
        ),
        _buildFilterBar(),
        Expanded(
          child: GridView.builder(
            padding: const EdgeInsets.all(16.0),
            gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
              crossAxisCount: 3,
              crossAxisSpacing: 12,
              mainAxisSpacing: 12,
              childAspectRatio: 1.2,
            ),
            itemCount: _filteredWallets.length,
            itemBuilder: (context, index) {
              return _buildWalletTile(_filteredWallets[index]);
            },
          ),
        ),
      ],
    );
  }

  Widget _buildGoalsTab() {
    return GridView.builder(
      padding: const EdgeInsets.all(16.0),
      gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
        crossAxisCount: 2,
        crossAxisSpacing: 16,
        mainAxisSpacing: 16,
        childAspectRatio: 0.9,
      ),
      itemCount: _goalWallets.length,
      itemBuilder: (context, index) {
        return _buildWalletTile(_goalWallets[index]);
      },
    );
  }

  Widget _buildBudgetsTab() {
    return const Center(child: Text('Budgets feature coming soon!'));
  }

  Widget _buildFilterBar() {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16.0, vertical: 8.0),
      color: Colors.white,
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          const Text(
            'Wallet Category',
            style: TextStyle(fontWeight: FontWeight.bold),
          ),
          DropdownButton<String>(
            value: _selectedCategory,
            underline: const SizedBox(),
            items: ['All', 'Expense', 'Investment']
                .map(
                  (label) => DropdownMenuItem(value: label, child: Text(label)),
                )
                .toList(),
            onChanged: (value) {
              if (value != null) {
                setState(() {
                  _selectedCategory = value;
                  _applyFilter();
                });
              }
            },
          ),
        ],
      ),
    );
  }

  Widget _buildWalletTile(Wallet wallet) {
    if (wallet.category == 'Goal') {
      return _buildGoalWalletTile(wallet);
    }

    final currencyFormat = NumberFormat.currency(locale: 'en_IN', symbol: '₹');
    return GestureDetector(
      onTap: () async {
        final result = await Navigator.pushNamed(
          context,
          '/configure_wallet',
          arguments: wallet.id,
        );
        if (result == true) _fetchWallets();
      },
      child: Container(
        decoration: BoxDecoration(
          color: _getWalletColor(wallet.category),
          borderRadius: BorderRadius.circular(12),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withOpacity(0.1),
              blurRadius: 4,
              offset: const Offset(0, 2),
            ),
          ],
        ),
        child: Padding(
          padding: const EdgeInsets.all(8.0),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                wallet.walletName,
                style: const TextStyle(
                  color: Colors.white,
                  fontWeight: FontWeight.bold,
                ),
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
              ),
              const SizedBox(height: 4),
              Text(
                currencyFormat.format(wallet.balance),
                style: const TextStyle(color: Colors.white, fontSize: 16),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildGoalWalletTile(Wallet wallet) {
    final currencyFormat = NumberFormat.currency(
      locale: 'en_IN',
      symbol: '₹',
      decimalDigits: 0,
    );
    final target = wallet.targetAmount ?? 0.0;
    final balance = wallet.balance;
    final progress = (target > 0) ? (balance / target).clamp(0.0, 1.0) : 0.0;
    final percentage = (progress * 100).toStringAsFixed(0);

    return GestureDetector(
      onTap: () async {
        final result = await Navigator.pushNamed(
          context,
          '/configure_wallet',
          arguments: wallet.id,
        );
        if (result == true) _fetchWallets();
      },
      child: Container(
        decoration: BoxDecoration(
          color: _getWalletColor(wallet.category),
          borderRadius: BorderRadius.circular(12),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withOpacity(0.1),
              blurRadius: 4,
              offset: const Offset(0, 2),
            ),
          ],
        ),
        child: Padding(
          padding: const EdgeInsets.all(12.0),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                wallet.walletName,
                style: const TextStyle(
                  color: Colors.white,
                  fontWeight: FontWeight.bold,
                  fontSize: 16,
                ),
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
              ),
              const Spacer(),
              Text(
                '${currencyFormat.format(balance)} / ${currencyFormat.format(target)}',
                style: const TextStyle(color: Colors.white70, fontSize: 14),
              ),
              const SizedBox(height: 4),
              ClipRRect(
                borderRadius: BorderRadius.circular(10),
                child: LinearProgressIndicator(
                  value: progress,
                  backgroundColor: Colors.white.withOpacity(0.3),
                  valueColor: const AlwaysStoppedAnimation<Color>(Colors.white),
                  minHeight: 8,
                ),
              ),
              const SizedBox(height: 4),
              Align(
                alignment: Alignment.centerRight,
                child: Text(
                  '$percentage% Complete',
                  style: const TextStyle(
                    color: Colors.white,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Color _getWalletColor(String category) {
    switch (category) {
      case 'Expense':
        return Colors.red;
      case 'Investment':
        return Colors.green;
      case 'Goal':
        return const Color(0xFF0D256E);
      default:
        return Colors.grey;
    }
  }
}
