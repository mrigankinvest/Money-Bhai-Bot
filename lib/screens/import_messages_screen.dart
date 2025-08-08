import 'package:flutter/material.dart';

class ImportMessagesScreen extends StatelessWidget {
  const ImportMessagesScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Import From Messages'),
        backgroundColor: const Color(0xFF0D256E),
        foregroundColor: Colors.white,
      ),
      body: const Center(
        child: Text(
          'Import Messages UI will be built here.',
          style: TextStyle(fontSize: 18),
        ),
      ),
    );
  }
}
