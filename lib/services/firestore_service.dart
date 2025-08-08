import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:firebase_auth/firebase_auth.dart';
import '../models/wallet_model.dart';
import '../models/transaction_model.dart' as model;

class FirestoreService {
  final FirebaseFirestore _db = FirebaseFirestore.instance;
  final FirebaseAuth _auth = FirebaseAuth.instance;

  String? get _userId => _auth.currentUser?.uid;

  // --- Wallet Methods (existing code) ---
  Future<List<Wallet>> getWallets() async {
    if (_userId == null) return [];
    try {
      final snapshot = await _db
          .collection('users')
          .doc(_userId)
          .collection('wallets')
          .get();
      if (snapshot.docs.isEmpty) {
        await addDefaultWallet(_userId!);
        final newSnapshot = await _db
            .collection('users')
            .doc(_userId)
            .collection('wallets')
            .get();
        return newSnapshot.docs
            .map((doc) => Wallet.fromFirestore(doc))
            .toList();
      }
      return snapshot.docs.map((doc) => Wallet.fromFirestore(doc)).toList();
    } catch (e) {
      print("Error fetching wallets: $e");
      return [];
    }
  }

  Future<Wallet?> getWalletById(String walletId) async {
    if (_userId == null) return null;
    try {
      final doc = await _db
          .collection('users')
          .doc(_userId)
          .collection('wallets')
          .doc(walletId)
          .get();
      if (doc.exists) {
        return Wallet.fromFirestore(doc);
      }
    } catch (e) {
      print("Error fetching wallet by ID: $e");
    }
    return null;
  }

  Future<void> addDefaultWallet(String userId) async {
    try {
      await _db.collection('users').doc(userId).collection('wallets').add({
        'walletName': 'Cash Wallet',
        'balance': 0.0,
        'category': 'Expense',
        'createdAt': FieldValue.serverTimestamp(),
      });
    } catch (e) {
      print("Error creating default wallet: $e");
    }
  }

  Future<void> addWallet({
    required String name,
    required String category,
    required double initialBalance,
    double? targetAmount,
  }) async {
    if (_userId == null) return;
    try {
      final data = <String, dynamic>{
        'walletName': name,
        'balance': initialBalance,
        'category': category,
        'createdAt': FieldValue.serverTimestamp(),
      };
      if (targetAmount != null) {
        data['targetAmount'] = targetAmount;
      }
      await _db
          .collection('users')
          .doc(_userId)
          .collection('wallets')
          .add(data);
    } catch (e) {
      print("Error adding wallet: $e");
    }
  }

  Future<void> updateWallet(
    String walletId, {
    required String name,
    required String category,
    required double balance,
    double? targetAmount,
  }) async {
    if (_userId == null) return;
    try {
      final data = <String, dynamic>{
        'walletName': name,
        'balance': balance,
        'category': category,
      };
      if (targetAmount != null) {
        data['targetAmount'] = targetAmount;
      }
      await _db
          .collection('users')
          .doc(_userId)
          .collection('wallets')
          .doc(walletId)
          .update(data);
    } catch (e) {
      print("Error updating wallet: $e");
    }
  }

  Future<void> deleteWallet(String walletId) async {
    if (_userId == null) return;
    try {
      await _db
          .collection('users')
          .doc(_userId)
          .collection('wallets')
          .doc(walletId)
          .delete();
    } catch (e) {
      print("Error deleting wallet: $e");
    }
  }
  // --- End of Wallet Methods ---

  // --- Transaction Methods ---

  Future<List<model.Transaction>> getTransactionsForMonth(
    DateTime month,
  ) async {
    if (_userId == null) return [];
    try {
      final startOfMonth = DateTime(month.year, month.month, 1);
      final endOfMonth = DateTime(month.year, month.month + 1, 0, 23, 59, 59);

      final snapshot = await _db
          .collection('users')
          .doc(_userId)
          .collection('transactions')
          .where('date', isGreaterThanOrEqualTo: startOfMonth)
          .where('date', isLessThanOrEqualTo: endOfMonth)
          .orderBy('date', descending: true)
          .get();

      // --- FIX: Use the 'model.' prefix here as well ---
      return snapshot.docs
          .map((doc) => model.Transaction.fromFirestore(doc))
          .toList();
    } catch (e) {
      print("Error fetching transactions: $e");
      return [];
    }
  }

  // --- NEW: Add a Transaction using a Firestore Transaction ---
  Future<bool> addTransaction(Map<String, dynamic> transactionData) async {
    if (_userId == null) return false;

    final fromWalletId = transactionData['fromWalletId'] as String?;
    final toWalletId = transactionData['toWalletId'] as String?;
    final linkedGoalId = transactionData['linkedGoalId'] as String?;
    final amount = transactionData['amount'] as double;
    final type = transactionData['type'] as String;

    try {
      // The 'transaction' parameter here refers to the Firestore Transaction, not your model.
      // This is why the prefix is necessary.
      await _db.runTransaction((transaction) async {
        // 1. Create the new transaction document
        final newTransactionRef = _db
            .collection('users')
            .doc(_userId)
            .collection('transactions')
            .doc();
        transaction.set(newTransactionRef, transactionData);

        // 2. Update 'from' wallet balance (for Expense, Investment, Transfer)
        if (fromWalletId != null) {
          final fromWalletRef = _db
              .collection('users')
              .doc(_userId)
              .collection('wallets')
              .doc(fromWalletId);
          transaction.update(fromWalletRef, {
            'balance': FieldValue.increment(-amount),
          });
        }

        // 3. Update 'to' wallet balance (for Income, Transfer)
        if (toWalletId != null) {
          final toWalletRef = _db
              .collection('users')
              .doc(_userId)
              .collection('wallets')
              .doc(toWalletId);
          transaction.update(toWalletRef, {
            'balance': FieldValue.increment(amount),
          });
        }

        // 4. (Conditional) Update linked goal balance
        if (type == 'Investment' && linkedGoalId != null) {
          final goalWalletRef = _db
              .collection('users')
              .doc(_userId)
              .collection('wallets')
              .doc(linkedGoalId);
          transaction.update(goalWalletRef, {
            'balance': FieldValue.increment(amount),
          });
        }
      });
      return true;
    } catch (e) {
      print("Transaction failed: $e");
      return false;
    }
  }

  // --- NEW: Get a single transaction by its ID ---
  Future<model.Transaction?> getTransactionById(String transactionId) async {
    if (_userId == null) return null;
    try {
      final doc = await _db
          .collection('users')
          .doc(_userId)
          .collection('transactions')
          .doc(transactionId)
          .get();
      if (doc.exists) {
        return model.Transaction.fromFirestore(doc);
      }
    } catch (e) {
      print("Error fetching transaction by ID: $e");
    }
    return null;
  }

  // --- NEW: Update a Transaction using a Firestore Transaction ---
  Future<bool> updateTransaction(
    String transactionId,
    Map<String, dynamic> newData,
    model.Transaction oldData,
  ) async {
    if (_userId == null) return false;

    try {
      await _db.runTransaction((transaction) async {
        final transactionRef = _db
            .collection('users')
            .doc(_userId)
            .collection('transactions')
            .doc(transactionId);
        final walletsRef = _db
            .collection('users')
            .doc(_userId)
            .collection('wallets');

        // 1. Reverse the old transaction's effect on wallet balances
        if (oldData.fromWalletId != null) {
          transaction.update(walletsRef.doc(oldData.fromWalletId!), {
            'balance': FieldValue.increment(oldData.amount),
          });
        }
        if (oldData.toWalletId != null) {
          transaction.update(walletsRef.doc(oldData.toWalletId!), {
            'balance': FieldValue.increment(-oldData.amount),
          });
        }
        if (oldData.type == 'Investment' && oldData.linkedGoalId != null) {
          final oldAmount = oldData.subType == 'Invest / Buy'
              ? -oldData.amount
              : oldData.amount;
          transaction.update(walletsRef.doc(oldData.linkedGoalId!), {
            'balance': FieldValue.increment(oldAmount),
          });
        }

        // 2. Apply the new transaction's effect on wallet balances
        final newAmount = newData['amount'] as double;
        if (newData['fromWalletId'] != null) {
          transaction.update(walletsRef.doc(newData['fromWalletId']), {
            'balance': FieldValue.increment(-newAmount),
          });
        }
        if (newData['toWalletId'] != null) {
          transaction.update(walletsRef.doc(newData['toWalletId']), {
            'balance': FieldValue.increment(newAmount),
          });
        }
        if (newData['type'] == 'Investment' &&
            newData['linkedGoalId'] != null) {
          final newAmountForGoal = newData['subType'] == 'Invest / Buy'
              ? newAmount
              : -newAmount;
          transaction.update(walletsRef.doc(newData['linkedGoalId']), {
            'balance': FieldValue.increment(newAmountForGoal),
          });
        }

        // 3. Finally, update the transaction document itself
        transaction.update(transactionRef, newData);
      });
      return true;
    } catch (e) {
      print("Update transaction failed: $e");
      return false;
    }
  }

  // --- NEW: Delete one or more transactions using a Batched Write ---
  Future<bool> deleteTransactions(Set<String> transactionIds) async {
    if (_userId == null || transactionIds.isEmpty) return false;

    try {
      final batch = _db.batch();
      final transactionsRef = _db
          .collection('users')
          .doc(_userId)
          .collection('transactions');
      final walletsRef = _db
          .collection('users')
          .doc(_userId)
          .collection('wallets');

      final Map<String, double> walletUpdates = {};

      for (final id in transactionIds) {
        final doc = await transactionsRef.doc(id).get();
        if (doc.exists) {
          final txn = model.Transaction.fromFirestore(doc);

          // Calculate the reversal effect
          if (txn.fromWalletId != null) {
            walletUpdates[txn.fromWalletId!] =
                (walletUpdates[txn.fromWalletId] ?? 0) + txn.amount;
          }
          if (txn.toWalletId != null) {
            walletUpdates[txn.toWalletId!] =
                (walletUpdates[txn.toWalletId] ?? 0) - txn.amount;
          }
          if (txn.type == 'Investment' && txn.linkedGoalId != null) {
            final amountToReverse = txn.subType == 'Invest / Buy'
                ? -txn.amount
                : txn.amount;
            walletUpdates[txn.linkedGoalId!] =
                (walletUpdates[txn.linkedGoalId] ?? 0) + amountToReverse;
          }

          batch.delete(transactionsRef.doc(id));
        }
      }

      walletUpdates.forEach((walletId, change) {
        batch.update(walletsRef.doc(walletId), {
          'balance': FieldValue.increment(change),
        });
      });

      await batch.commit();
      return true;
    } catch (e) {
      print("Batch delete failed: $e");
      return false;
    }
  }
}
