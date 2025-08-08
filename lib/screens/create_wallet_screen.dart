import 'package:flutter/material.dart';
import '../services/firestore_service.dart';

class CreateWalletScreen extends StatefulWidget {
  const CreateWalletScreen({super.key});

  @override
  State<CreateWalletScreen> createState() => _CreateWalletScreenState();
}

class _CreateWalletScreenState extends State<CreateWalletScreen> {
  final _formKey = GlobalKey<FormState>();
  final _nameController = TextEditingController();
  final _balanceController = TextEditingController();
  final _targetController =
      TextEditingController(); // Controller for target amount
  String _selectedCategory = 'Expense';
  String _selectedCurrency = 'INR';
  bool _isLoading = false;

  final FirestoreService _firestoreService = FirestoreService();

  @override
  void dispose() {
    _nameController.dispose();
    _balanceController.dispose();
    _targetController.dispose();
    super.dispose();
  }

  void _submitForm() async {
    if (_formKey.currentState!.validate()) {
      setState(() => _isLoading = true);
      await _firestoreService.addWallet(
        name: _nameController.text,
        category: _selectedCategory,
        initialBalance: double.tryParse(_balanceController.text) ?? 0.0,
        // Pass target amount only if the category is 'Goal'
        targetAmount: _selectedCategory == 'Goal'
            ? double.tryParse(_targetController.text)
            : null,
      );
      if (mounted) {
        Navigator.pop(context, true); // Return true to indicate success
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('New Account'),
        backgroundColor: const Color(0xFF0D256E),
        foregroundColor: Colors.white,
        actions: [
          IconButton(onPressed: () {}, icon: const Icon(Icons.bookmark_border)),
        ],
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(24.0),
        child: Form(
          key: _formKey,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                'CREATE NEW\nWALLET',
                style: TextStyle(
                  fontSize: 36,
                  fontWeight: FontWeight.bold,
                  color: Color(0xFF0D256E),
                ),
              ),
              const SizedBox(height: 8),
              const Text(
                "Let's start financial well being",
                style: TextStyle(fontSize: 16, color: Colors.grey),
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
                label: 'Initial Balance:',
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
                onPressed: _isLoading ? null : _submitForm,
                style: ElevatedButton.styleFrom(
                  backgroundColor: const Color(0xFFB2C832),
                  foregroundColor: const Color(0xFF0D256E),
                ),
                child: _isLoading
                    ? const CircularProgressIndicator()
                    : const Text('Submit'),
              ),
            ],
          ),
        ),
      ),
    );
  }

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
