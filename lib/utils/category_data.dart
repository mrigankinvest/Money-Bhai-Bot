import 'package:flutter/material.dart';

// A reusable data class for our categories, now with color
class TransactionCategory {
  final String name;
  final IconData icon;
  final Color color; // <-- NEW: Color property
  const TransactionCategory(this.name, this.icon, this.color);
}

// A central map of all categories, accessible from anywhere in the app.
const Map<String, List<TransactionCategory>> masterCategories = {
  'Income': [
    TransactionCategory('Salary', Icons.work_outline, Colors.green),
    TransactionCategory(
      'Freelance',
      Icons.business_center_outlined,
      Colors.blue,
    ),
    TransactionCategory('Investment Returns', Icons.show_chart, Colors.purple),
    TransactionCategory('Bonus', Icons.emoji_events_outlined, Colors.amber),
    TransactionCategory('Gift', Icons.card_giftcard_outlined, Colors.pink),
    TransactionCategory('Other', Icons.category_outlined, Colors.grey),
  ],
  'Expense': [
    TransactionCategory(
      'Food & Drinks',
      Icons.fastfood_outlined,
      Colors.orange,
    ),
    TransactionCategory(
      'Shopping',
      Icons.shopping_bag_outlined,
      Colors.pinkAccent,
    ),
    TransactionCategory(
      'Transport',
      Icons.directions_bus_outlined,
      Colors.blueAccent,
    ),
    TransactionCategory(
      'Bills & Utilities',
      Icons.receipt_long_outlined,
      Colors.lightBlue,
    ),
    TransactionCategory('Housing', Icons.home_outlined, Colors.brown),
    TransactionCategory('Health', Icons.healing_outlined, Colors.redAccent),
    TransactionCategory(
      'Entertainment',
      Icons.movie_outlined,
      Colors.deepPurple,
    ),
    TransactionCategory('Travel', Icons.flight_takeoff_outlined, Colors.teal),
    TransactionCategory('Family', Icons.people_outline, Colors.cyan),
    TransactionCategory('Education', Icons.school_outlined, Colors.indigo),
    TransactionCategory('Pets', Icons.pets_outlined, Colors.lime),
    TransactionCategory('Other', Icons.category_outlined, Colors.grey),
  ],
  'Transfer': [
    TransactionCategory('Savings', Icons.savings_outlined, Colors.green),
    TransactionCategory('Loan Payment', Icons.payment_outlined, Colors.red),
    TransactionCategory('General Transfer', Icons.swap_horiz, Colors.blueGrey),
  ],
  'Investment': [
    TransactionCategory(
      'Stocks',
      Icons.candlestick_chart_outlined,
      Colors.purple,
    ),
    TransactionCategory(
      'Mutual Funds',
      Icons.donut_large_outlined,
      Colors.deepOrange,
    ),
    TransactionCategory('Crypto', Icons.currency_bitcoin, Colors.amber),
    TransactionCategory('Real Estate', Icons.home_work_outlined, Colors.brown),
    TransactionCategory('Other', Icons.category_outlined, Colors.grey),
  ],
};

// A helper function to easily look up a category's details by its name.
TransactionCategory getCategoryDetails(String categoryName) {
  for (var categoryList in masterCategories.values) {
    for (var category in categoryList) {
      if (category.name == categoryName) {
        return category;
      }
    }
  }
  // Return a default category if no match is found
  return const TransactionCategory('Other', Icons.help_outline, Colors.grey);
}
