import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../models/wallet_model.dart';
import '../models/transaction_model.dart';
import '../services/firestore_service.dart';

// Data structure for categories with icons
class TransactionCategory {
  final String name;
  final IconData icon;
  const TransactionCategory(this.name, this.icon);
}

class EditTransactionScreen extends StatefulWidget {
  final String transactionId;
  const EditTransactionScreen({super.key, required this.transactionId});

  @override
  State<EditTransactionScreen> createState() => _EditTransactionScreenState();
}

class _EditTransactionScreenState extends State<EditTransactionScreen>
    with SingleTickerProviderStateMixin {
  final _formKey = GlobalKey<FormState>();
  final _amountController = TextEditingController();
  final _descriptionController = TextEditingController();
  DateTime _selectedDate = DateTime.now();

  List<Wallet> _allWallets = [];
  List<Wallet> _goalWallets = [];
  List<Wallet> _investmentWallets = [];
  List<Wallet> _cashFlowWallets = [];
  Wallet? _fromWallet;
  Wallet? _toWallet;
  Wallet? _linkedGoal;
  bool _isLoading = true;

  late TabController _tabController;
  TransactionCategory? _selectedCategory;
  String _investmentSubType = 'Invest / Buy';

  Transaction? _originalTransaction;

  static const Map<String, List<TransactionCategory>> _categories = {
    'Income': [
      TransactionCategory('Salary', Icons.work_outline),
      TransactionCategory('Freelance', Icons.business_center_outlined),
      TransactionCategory('Investment Returns', Icons.show_chart),
      TransactionCategory('Bonus', Icons.emoji_events_outlined),
      TransactionCategory('Gift', Icons.card_giftcard_outlined),
      TransactionCategory('Other', Icons.category_outlined),
    ],
    'Expense': [
      TransactionCategory('Food & Drinks', Icons.fastfood_outlined),
      TransactionCategory('Shopping', Icons.shopping_bag_outlined),
      TransactionCategory('Transport', Icons.directions_bus_outlined),
      TransactionCategory('Bills & Utilities', Icons.receipt_long_outlined),
      TransactionCategory('Housing', Icons.home_outlined),
      TransactionCategory('Health', Icons.healing_outlined),
      TransactionCategory('Entertainment', Icons.movie_outlined),
      TransactionCategory('Travel', Icons.flight_takeoff_outlined),
      TransactionCategory('Family', Icons.people_outline),
      TransactionCategory('Education', Icons.school_outlined),
      TransactionCategory('Pets', Icons.pets_outlined),
      TransactionCategory('Other', Icons.category_outlined),
    ],
    'Transfer': [
      TransactionCategory('Savings', Icons.savings_outlined),
      TransactionCategory('Loan Payment', Icons.payment_outlined),
      TransactionCategory('General Transfer', Icons.swap_horiz),
    ],
    'Investment': [
      TransactionCategory('Stocks', Icons.candlestick_chart_outlined),
      TransactionCategory('Mutual Funds', Icons.donut_large_outlined),
      TransactionCategory('Crypto', Icons.currency_bitcoin),
      TransactionCategory('Real Estate', Icons.home_work_outlined),
      TransactionCategory('Other', Icons.category_outlined),
    ],
  };

  final FirestoreService _firestoreService = FirestoreService();

  @override
  void initState() {
    super.initState();
    _loadInitialData();
  }

  @override
  void dispose() {
    _tabController.dispose();
    _amountController.dispose();
    _descriptionController.dispose();
    super.dispose();
  }

  // Helper function to safely find a wallet by ID
  Wallet? _findWalletById(String? id) {
    if (id == null) return null;
    try {
      return _allWallets.firstWhere((wallet) => wallet.id == id);
    } catch (e) {
      return null; // Return null if not found
    }
  }

  Future<void> _loadInitialData() async {
    _originalTransaction = await _firestoreService.getTransactionById(
      widget.transactionId,
    );
    if (_originalTransaction == null) {
      if (mounted) Navigator.pop(context);
      return;
    }

    _allWallets = await _firestoreService.getWallets();
    _goalWallets = _allWallets.where((w) => w.category == 'Goal').toList();
    _investmentWallets = _allWallets
        .where((w) => w.category == 'Investment')
        .toList();
    _cashFlowWallets = _allWallets
        .where((w) => w.category == 'Expense')
        .toList();

    _fromWallet = _findWalletById(_originalTransaction!.fromWalletId);
    _toWallet = _findWalletById(_originalTransaction!.toWalletId);
    _linkedGoal = _findWalletById(_originalTransaction!.linkedGoalId);

    _amountController.text = _originalTransaction!.amount.toString();
    _descriptionController.text = _originalTransaction!.description;
    _selectedDate = _originalTransaction!.date;

    if (_originalTransaction!.subType != null) {
      _investmentSubType = _originalTransaction!.subType!;
    }

    final categoryName = _originalTransaction!.category;
    if (categoryName != null) {
      final categoriesForType = _categories[_originalTransaction!.type] ?? [];
      // --- THIS IS THE FIX ---
      // Use a try-catch block for a safer way to find the category.
      try {
        _selectedCategory = categoriesForType.firstWhere(
          (c) => c.name == categoryName,
        );
      } catch (e) {
        _selectedCategory = null; // Safely assign null if not found
      }
    }

    _tabController = TabController(
      length: 4,
      vsync: this,
      initialIndex: [
        'Income',
        'Expense',
        'Transfer',
        'Investment',
      ].indexOf(_originalTransaction!.type),
    );
    _tabController.addListener(_handleTabSelection);

    setState(() => _isLoading = false);
  }

  void _handleTabSelection() {
    if (_tabController.indexIsChanging) return;
    setState(() {
      _selectedCategory = null;
      _fromWallet = null;
      _toWallet = null;
      _linkedGoal = null;
      _formKey.currentState?.reset();
      _amountController.clear();
      _descriptionController.clear();
    });
  }

  Future<void> _updateTransaction() async {
    if (_formKey.currentState!.validate()) {
      setState(() => _isLoading = true);
      String currentTabType = [
        'Income',
        'Expense',
        'Transfer',
        'Investment',
      ][_tabController.index];

      final newData = <String, dynamic>{
        'type': currentTabType,
        'amount': double.parse(_amountController.text),
        'description': _descriptionController.text,
        'date': _selectedDate,
        'fromWalletId': _fromWallet?.id,
        'toWalletId': _toWallet?.id,
        'fromWalletName': _fromWallet?.walletName,
        'toWalletName': _toWallet?.walletName,
        'linkedGoalId': _linkedGoal?.id,
        'category': _selectedCategory?.name,
        'subType': currentTabType == 'Investment' ? _investmentSubType : null,
      };

      final success = await _firestoreService.updateTransaction(
        widget.transactionId,
        newData,
        _originalTransaction!,
      );

      if (mounted) {
        if (success) {
          Navigator.pop(context, true); // Return true to refresh list
        } else {
          setState(() => _isLoading = false);
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Failed to update transaction.')),
          );
        }
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_isLoading) {
      return Scaffold(
        appBar: AppBar(title: const Text('Edit Transaction')),
        body: const Center(child: CircularProgressIndicator()),
      );
    }

    String currentTabType = [
      'Income',
      'Expense',
      'Transfer',
      'Investment',
    ][_tabController.index];

    return Scaffold(
      appBar: AppBar(
        title: const Text('Edit Transaction'),
        backgroundColor: Colors.white,
        foregroundColor: Colors.black,
        elevation: 1,
        actions: [
          IconButton(
            icon: const Icon(Icons.check, color: Color(0xFF0D256E)),
            onPressed: _updateTransaction,
          ),
        ],
        bottom: TabBar(
          controller: _tabController,
          labelColor: const Color(0xFF0D256E),
          unselectedLabelColor: Colors.grey,
          indicatorColor: const Color(0xFF0D256E),
          isScrollable: true,
          tabs: const [
            Tab(text: 'Income'),
            Tab(text: 'Expense'),
            Tab(text: 'Transfer'),
            Tab(text: 'Investment'),
          ],
        ),
      ),
      body: Form(
        key: _formKey,
        child: ListView(
          padding: const EdgeInsets.all(16.0),
          children: [
            _buildTappableField(
              label: 'Date',
              value: DateFormat('dd/MM/yy (EEE) hh:mm a').format(_selectedDate),
              onTap: () async {
                final date = await showDatePicker(
                  context: context,
                  initialDate: _selectedDate,
                  firstDate: DateTime(2020),
                  lastDate: DateTime.now(),
                );
                if (date != null) {
                  setState(() => _selectedDate = date);
                }
              },
            ),
            _buildAmountField(),
            if (currentTabType == 'Investment') _buildInvestmentTypeSelector(),
            _buildTappableField(
              label: 'Category',
              value: _selectedCategory?.name ?? 'Select Category',
              onTap: () => _showCategoryPicker(currentTabType),
            ),
            _buildWalletSelectors(currentTabType),
            _buildDescriptionField(),
            if (currentTabType == 'Investment' &&
                _investmentSubType == 'Invest / Buy')
              _buildGoalSelector(),
          ],
        ),
      ),
    );
  }

  // --- All helper methods below are identical to AddTransactionScreen ---

  void _showCategoryPicker(String transactionType) {
    final relevantCategories = _categories[transactionType] ?? [];
    showModalBottomSheet(
      context: context,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (context) {
        return Padding(
          padding: const EdgeInsets.all(16.0),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                'Select Category',
                style: Theme.of(context).textTheme.titleLarge,
              ),
              const SizedBox(height: 16),
              Expanded(
                child: GridView.builder(
                  gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                    crossAxisCount: 4,
                    crossAxisSpacing: 12,
                    mainAxisSpacing: 12,
                  ),
                  itemCount: relevantCategories.length,
                  itemBuilder: (context, index) {
                    final category = relevantCategories[index];
                    return InkWell(
                      onTap: () {
                        setState(() => _selectedCategory = category);
                        Navigator.pop(context);
                      },
                      borderRadius: BorderRadius.circular(8),
                      child: Column(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          Icon(category.icon, size: 32),
                          const SizedBox(height: 8),
                          Text(
                            category.name,
                            textAlign: TextAlign.center,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                          ),
                        ],
                      ),
                    );
                  },
                ),
              ),
            ],
          ),
        );
      },
    );
  }

  void _showWalletPicker({
    required String title,
    required List<Wallet> wallets,
    required Function(Wallet) onSelected,
  }) {
    showModalBottomSheet(
      context: context,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (context) {
        return Padding(
          padding: const EdgeInsets.all(16.0),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(title, style: Theme.of(context).textTheme.titleLarge),
              const SizedBox(height: 16),
              Expanded(
                child: ListView.builder(
                  itemCount: wallets.length,
                  itemBuilder: (context, index) {
                    final wallet = wallets[index];
                    return ListTile(
                      title: Text(wallet.walletName),
                      onTap: () {
                        onSelected(wallet);
                        Navigator.pop(context);
                      },
                    );
                  },
                ),
              ),
            ],
          ),
        );
      },
    );
  }

  Widget _buildInvestmentTypeSelector() {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8.0),
      child: SegmentedButton<String>(
        segments: const <ButtonSegment<String>>[
          ButtonSegment<String>(
            value: 'Invest / Buy',
            label: Text('Invest / Buy'),
          ),
          ButtonSegment<String>(
            value: 'Withdraw / Sell',
            label: Text('Withdraw / Sell'),
          ),
        ],
        selected: {_investmentSubType},
        onSelectionChanged: (Set<String> newSelection) {
          setState(() {
            _investmentSubType = newSelection.first;
            _fromWallet = null;
            _toWallet = null;
          });
        },
      ),
    );
  }

  Widget _buildWalletSelectors(String currentTabType) {
    switch (currentTabType) {
      case 'Income':
        return _buildTappableField(
          label: 'To Account',
          value: _toWallet?.walletName ?? 'Select Account',
          onTap: () => _showWalletPicker(
            title: 'Select Account',
            wallets: _cashFlowWallets,
            onSelected: (w) => setState(() => _toWallet = w),
          ),
        );
      case 'Expense':
        return _buildTappableField(
          label: 'From Account',
          value: _fromWallet?.walletName ?? 'Select Account',
          onTap: () => _showWalletPicker(
            title: 'Select Account',
            wallets: _cashFlowWallets,
            onSelected: (w) => setState(() => _fromWallet = w),
          ),
        );
      case 'Transfer':
        return Column(
          children: [
            _buildTappableField(
              label: 'From Account',
              value: _fromWallet?.walletName ?? 'Select Account',
              onTap: () => _showWalletPicker(
                title: 'Select From Account',
                wallets: _cashFlowWallets,
                onSelected: (w) => setState(() => _fromWallet = w),
              ),
            ),
            _buildTappableField(
              label: 'To Account',
              value: _toWallet?.walletName ?? 'Select Account',
              onTap: () => _showWalletPicker(
                title: 'Select To Account',
                wallets: _cashFlowWallets
                    .where((w) => w.id != _fromWallet?.id)
                    .toList(),
                onSelected: (w) => setState(() => _toWallet = w),
              ),
            ),
          ],
        );
      case 'Investment':
        if (_investmentSubType == 'Invest / Buy') {
          return Column(
            children: [
              _buildTappableField(
                label: 'From Account (Cash)',
                value: _fromWallet?.walletName ?? 'Select Account',
                onTap: () => _showWalletPicker(
                  title: 'Select Cash Account',
                  wallets: _cashFlowWallets,
                  onSelected: (w) => setState(() => _fromWallet = w),
                ),
              ),
              _buildTappableField(
                label: 'To Account (Investment)',
                value: _toWallet?.walletName ?? 'Select Account',
                onTap: () => _showWalletPicker(
                  title: 'Select Investment Account',
                  wallets: _investmentWallets,
                  onSelected: (w) => setState(() => _toWallet = w),
                ),
              ),
            ],
          );
        } else {
          // Withdraw / Sell
          return Column(
            children: [
              _buildTappableField(
                label: 'From Account (Investment)',
                value: _fromWallet?.walletName ?? 'Select Account',
                onTap: () => _showWalletPicker(
                  title: 'Select Investment Account',
                  wallets: _investmentWallets,
                  onSelected: (w) => setState(() => _fromWallet = w),
                ),
              ),
              _buildTappableField(
                label: 'To Account (Cash)',
                value: _toWallet?.walletName ?? 'Select Account',
                onTap: () => _showWalletPicker(
                  title: 'Select Cash Account',
                  wallets: _cashFlowWallets,
                  onSelected: (w) => setState(() => _toWallet = w),
                ),
              ),
            ],
          );
        }
      default:
        return const SizedBox.shrink();
    }
  }

  Widget _buildGoalSelector() {
    return _buildTappableField(
      label: 'Tag to Goal',
      value: _linkedGoal?.walletName ?? 'Optional',
      onTap: () => _showWalletPicker(
        title: 'Select Goal',
        wallets: _goalWallets,
        onSelected: (wallet) => setState(() => _linkedGoal = wallet),
      ),
    );
  }

  Widget _buildTappableField({
    required String label,
    required String value,
    required VoidCallback onTap,
  }) {
    return InkWell(
      onTap: onTap,
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 12.0),
        child: Row(
          children: [
            SizedBox(
              width: 80,
              child: Text(label, style: const TextStyle(color: Colors.grey)),
            ),
            Expanded(child: Text(value, style: const TextStyle(fontSize: 16))),
            const Icon(Icons.chevron_right, color: Colors.grey),
          ],
        ),
      ),
    );
  }

  Widget _buildAmountField() {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 12.0),
      child: Row(
        children: [
          const SizedBox(
            width: 80,
            child: Text('Amount', style: TextStyle(color: Colors.grey)),
          ),
          Expanded(
            child: TextFormField(
              controller: _amountController,
              decoration: const InputDecoration(
                hintText: '₹ 0.00',
                border: InputBorder.none,
                isDense: true,
              ),
              style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
              keyboardType: TextInputType.number,
              validator: (value) {
                if (value == null ||
                    value.isEmpty ||
                    double.tryParse(value) == null ||
                    double.parse(value) <= 0) {
                  return 'Please enter a valid amount';
                }
                return null;
              },
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildDescriptionField() {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 12.0),
      child: Row(
        children: [
          const SizedBox(
            width: 80,
            child: Text('Note', style: const TextStyle(color: Colors.grey)),
          ),
          Expanded(
            child: TextFormField(
              controller: _descriptionController,
              decoration: const InputDecoration(
                hintText: 'Add a note...',
                border: InputBorder.none,
                isDense: true,
              ),
              style: const TextStyle(fontSize: 16),
              validator: (value) =>
                  value == null || value.isEmpty ? 'Please enter a note' : null,
            ),
          ),
        ],
      ),
    );
  }
}
