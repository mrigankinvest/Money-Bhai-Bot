import 'package:cloud_firestore/cloud_firestore.dart';

class Transaction {
  final String id;
  final String type; // "Income", "Expense", "Investment", "Transfer"
  final double amount;
  final DateTime date;
  final String description;
  final String? fromWalletId;
  final String? toWalletId;
  final String? linkedGoalId;
  final String? fromWalletName;
  final String? toWalletName;
  final String? category;
  final String?
  subType; // <-- NEW FIELD: e.g., "Invest / Buy", "Withdraw / Sell"

  Transaction({
    required this.id,
    required this.type,
    required this.amount,
    required this.date,
    required this.description,
    this.fromWalletId,
    this.toWalletId,
    this.linkedGoalId,
    this.fromWalletName,
    this.toWalletName,
    this.category,
    this.subType, // <-- ADDED TO CONSTRUCTOR
  });

  factory Transaction.fromFirestore(DocumentSnapshot doc) {
    Map<String, dynamic> data = doc.data() as Map<String, dynamic>;
    return Transaction(
      id: doc.id,
      type: data['type'] ?? 'Expense',
      amount: (data['amount'] ?? 0.0).toDouble(),
      date: (data['date'] as Timestamp).toDate(),
      description: data['description'] ?? '',
      fromWalletId: data['fromWalletId'],
      toWalletId: data['toWalletId'],
      linkedGoalId: data['linkedGoalId'],
      fromWalletName: data['fromWalletName'],
      toWalletName: data['toWalletName'],
      category: data['category'],
      subType: data['subType'], // <-- ADDED FROM FIRESTORE
    );
  }
}
