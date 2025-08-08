import 'package:flutter/material.dart';

class ChatScreen extends StatelessWidget {
  const ChatScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Chat With Me'),
        backgroundColor: const Color(0xFF0D256E),
        foregroundColor: Colors.white,
      ),
      body: const Center(
        child: Text(
          'WhatsApp-style chat UI will be built here.',
          style: TextStyle(fontSize: 18),
        ),
      ),
    );
  }
}
