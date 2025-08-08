import 'package:flutter/material.dart';
import '../models/wallet_model.dart';
import '../services/firestore_service.dart';

class WalletConfigurationScreen extends StatefulWidget {
  const WalletConfigurationScreen({super.key});

  @override
  State<WalletConfigurationScreen> createState() =>
      _WalletConfigurationScreenState();
}

class _WalletConfigurationScreenState extends State<WalletConfigurationScreen> {
  final _formKey = GlobalKey<FormState>();
  final _nameController = TextEditingController();
  final _balanceController = TextEditingController();
  final _targetController =
      TextEditingController(); // Controller for target amount
  String _selectedCategory = 'Expense';
  String _selectedCurrency = 'INR';
  bool _isLoading = true;
  Wallet? _initialWallet;

  final FirestoreService _firestoreService = FirestoreService();

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final walletId = ModalRoute.of(context)!.settings.arguments as String?;
    if (walletId != null && _initialWallet == null) {
      _loadWalletData(walletId);
    } else if (walletId == null) {
      Navigator.pop(context);
    }
  }

  Future<void> _loadWalletData(String walletId) async {
    _initialWallet = await _firestoreService.getWalletById(walletId);
    if (_initialWallet != null) {
      _nameController.text = _initialWallet!.walletName;
      _balanceController.text = _initialWallet!.balance.toString();
      _selectedCategory = _initialWallet!.category;
      // Pre-fill target amount if it exists for the goal
      if (_initialWallet!.targetAmount != null) {
        _targetController.text = _initialWallet!.targetAmount.toString();
      }
      setState(() => _isLoading = false);
    } else {
      if (mounted) Navigator.pop(context);
    }
  }

  Future<void> _updateWallet() async {
    if (_formKey.currentState!.validate() && _initialWallet != null) {
      setState(() => _isLoading = true);
      await _firestoreService.updateWallet(
        _initialWallet!.id,
        name: _nameController.text,
        category: _selectedCategory,
        balance: double.tryParse(_balanceController.text) ?? 0.0,
        // Pass target amount only if the category is 'Goal'
        targetAmount: _selectedCategory == 'Goal'
            ? double.tryParse(_targetController.text)
            : null,
      );
      if (mounted) Navigator.pop(context, true); // Return true to refresh list
    }
  }

  Future<void> _deleteWallet() async {
    if (_initialWallet == null) return;

    final bool? confirm = await showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Delete Wallet'),
        content: const Text(
          'Are you sure you want to delete this wallet? This action cannot be undone.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Delete'),
          ),
        ],
      ),
    );

    if (confirm == true) {
      setState(() => _isLoading = true);
      await _firestoreService.deleteWallet(_initialWallet!.id);
      if (mounted) Navigator.pop(context, true);
    }
  }

  @override
  void dispose() {
    _nameController.dispose();
    _balanceController.dispose();
    _targetController.dispose(); // Dispose the new controller
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Configure Account'),
        backgroundColor: const Color(0xFF0D256E),
        foregroundColor: Colors.white,
        actions: [
          IconButton(onPressed: () {}, icon: const Icon(Icons.bookmark_border)),
        ],
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : SingleChildScrollView(
              padding: const EdgeInsets.all(24.0),
              child: Form(
                key: _formKey,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      'EDIT WALLET',
                      style: TextStyle(
                        fontSize: 36,
                        fontWeight: FontWeight.bold,
                        color: Color(0xFF0D256E),
                      ),
                    ),
                    const SizedBox(height: 40),
                    _buildTextField(
                      label: 'Account Name:',
                      controller: _nameController,
                    ),
                    const SizedBox(height: 24),
                    _buildDropdownField(
                      label: 'Category:',
                      value: _selectedCategory,
                      items: ['Expense', 'Investment', 'Goal'],
                      onChanged: (value) =>
                          setState(() => _selectedCategory = value!),
                    ),
                    const SizedBox(height: 24),
                    _buildTextField(
                      label: 'Balance:',
                      controller: _balanceController,
                      keyboardType: TextInputType.number,
                    ),
                    const SizedBox(height: 24),
                    // --- Conditionally show Target Amount field ---
                    if (_selectedCategory == 'Goal')
                      Padding(
                        padding: const EdgeInsets.only(bottom: 24.0),
                        child: _buildTextField(
                          label: 'Target Amount:',
                          controller: _targetController,
                          keyboardType: TextInputType.number,
                        ),
                      ),
                    _buildDropdownField(
                      label: 'Currency:',
                      value: _selectedCurrency,
                      items: ['INR', 'USD', 'EUR'],
                      onChanged: (value) =>
                          setState(() => _selectedCurrency = value!),
                    ),
                    const SizedBox(height: 40),
                    ElevatedButton(
                      onPressed: _updateWallet,
                      style: ElevatedButton.styleFrom(
                        backgroundColor: const Color(0xFFB2C832),
                        foregroundColor: const Color(0xFF0D256E),
                      ),
                      child: const Text('Submit'),
                    ),
                    const SizedBox(height: 24),
                    Center(
                      child: TextButton(
                        onPressed: _deleteWallet,
                        child: const Text(
                          'I want to delete this wallet',
                          style: TextStyle(
                            color: Colors.red,
                            decoration: TextDecoration.underline,
                          ),
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ),
    );
  }

  // Helper methods for form fields
  Widget _buildTextField({
    required String label,
    required TextEditingController controller,
    TextInputType keyboardType = TextInputType.text,
  }) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label, style: const TextStyle(fontWeight: FontWeight.bold)),
        TextFormField(
          controller: controller,
          keyboardType: keyboardType,
          decoration: const InputDecoration(border: UnderlineInputBorder()),
          validator: (value) {
            if (value == null || value.isEmpty) {
              return 'This field cannot be empty';
            }
            if (keyboardType == TextInputType.number &&
                double.tryParse(value) == null) {
              return 'Please enter a valid number';
            }
            return null;
          },
        ),
      ],
    );
  }

  Widget _buildDropdownField({
    required String label,
    required String value,
    required List<String> items,
    required ValueChanged<String?> onChanged,
  }) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label, style: const TextStyle(fontWeight: FontWeight.bold)),
        DropdownButtonFormField<String>(
          value: value,
          items: items.map((String value) {
            return DropdownMenuItem<String>(value: value, child: Text(value));
          }).toList(),
          onChanged: onChanged,
          decoration: const InputDecoration(border: UnderlineInputBorder()),
        ),
      ],
    );
  }
}
