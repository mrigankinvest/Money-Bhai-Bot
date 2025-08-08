import 'package:cloud_firestore/cloud_firestore.dart';

// Represents a single wallet in the app.
class Wallet {
  final String id;
  final String walletName;
  final double balance;
  final String category; // e.g., "Expense", "Investment", "Goal"
  final double? targetAmount; // Optional: Only for 'Goal' category

  Wallet({
    required this.id,
    required this.walletName,
    required this.balance,
    required this.category,
    this.targetAmount,
  });

  // A factory constructor to create a Wallet instance from a Firestore document.
  factory Wallet.fromFirestore(DocumentSnapshot doc) {
    Map<String, dynamic> data = doc.data() as Map<String, dynamic>;
    return Wallet(
      id: doc.id,
      walletName: data['walletName'] ?? 'Unnamed Wallet',
      balance: (data['balance'] ?? 0.0).toDouble(),
      category: data['category'] ?? 'Expense',
      targetAmount: (data['targetAmount'])
          ?.toDouble(), // Safely get target amount
    );
  }
}
