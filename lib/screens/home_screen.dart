import 'package:flutter/material.dart';
import 'package:flutter_slidable/flutter_slidable.dart';
import 'package:intl/intl.dart';
import 'package:table_calendar/table_calendar.dart';
import 'accounts_screen.dart';
import '../services/firestore_service.dart';
import '../models/transaction_model.dart';
import '../utils/category_data.dart';

// --- Placeholder Screens ---
class StatsScreen extends StatelessWidget {
  const StatsScreen({super.key});
  @override
  Widget build(BuildContext context) => const Scaffold(
    appBar: _CustomAppBar(title: 'Stats'),
    body: Center(child: Text('Stats Screen')),
  );
}

class MoreScreen extends StatelessWidget {
  const MoreScreen({super.key});
  @override
  Widget build(BuildContext context) => const Scaffold(
    appBar: _CustomAppBar(title: 'More'),
    body: Center(child: Text('More Screen')),
  );
}
// --- End of Placeholders ---

//############################################################################
// 1. HOME SCREEN (The Main Shell with Refresh Logic)
//############################################################################
class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});
  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  int _selectedIndex = 0;
  final GlobalKey<AccountsScreenState> _accountsScreenKey =
      GlobalKey<AccountsScreenState>();

  late final List<Widget> _widgetOptions;

  @override
  void initState() {
    super.initState();
    _widgetOptions = <Widget>[
      const TransactionsScreen(),
      const StatsScreen(),
      AccountsScreen(key: _accountsScreenKey),
      const MoreScreen(),
    ];
  }

  void _onItemTapped(int index) {
    if (index == 2) {
      _accountsScreenKey.currentState?.refreshData();
    }
    setState(() {
      _selectedIndex = index;
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: IndexedStack(index: _selectedIndex, children: _widgetOptions),
      bottomNavigationBar: BottomNavigationBar(
        currentIndex: _selectedIndex,
        onTap: _onItemTapped,
        type: BottomNavigationBarType.fixed,
        selectedItemColor: const Color(0xFF0D256E),
        unselectedItemColor: Colors.grey,
        selectedLabelStyle: const TextStyle(fontWeight: FontWeight.bold),
        items: const [
          BottomNavigationBarItem(
            icon: Icon(Icons.swap_horiz),
            label: 'Trans.',
          ),
          BottomNavigationBarItem(icon: Icon(Icons.bar_chart), label: 'Stats'),
          BottomNavigationBarItem(
            icon: Icon(Icons.account_balance_wallet_outlined),
            label: 'Accounts',
          ),
          BottomNavigationBarItem(icon: Icon(Icons.more_horiz), label: 'More'),
        ],
      ),
    );
  }
}

//############################################################################
// 2. TRANSACTIONS SCREEN (with ALL features)
//############################################################################
enum MenuState { closed, open }

class DailySummary {
  double income = 0.0;
  double expense = 0.0;
  double get net => income - expense;
}

class TransactionsScreen extends StatefulWidget {
  const TransactionsScreen({super.key});
  @override
  State<TransactionsScreen> createState() => _TransactionsScreenState();
}

class _TransactionsScreenState extends State<TransactionsScreen>
    with TickerProviderStateMixin {
  final FirestoreService _firestoreService = FirestoreService();
  late AnimationController _menuController;
  DateTime _selectedDate = DateTime.now();
  DateTime? _selectedDay;

  Map<DateTime, List<Transaction>> _groupedTransactions = {};
  Map<DateTime, DailySummary> _dailySummaries = {};
  Set<DateTime> _expandedDays = {};
  String _activeFilter = 'All';
  bool _isLoading = true;
  MenuState _menuState = MenuState.closed;

  double _totalIncome = 0.0;
  double _totalExpenses = 0.0;
  double _netInvestment = 0.0;

  bool _isMultiSelectMode = false;
  Set<String> _selectedTransactionIds = {};

  @override
  void initState() {
    super.initState();
    _selectedDay = _selectedDate;
    _menuController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 300),
    );
    _fetchAndProcessTransactions();
  }

  @override
  void dispose() {
    _menuController.dispose();
    super.dispose();
  }

  Future<void> _fetchAndProcessTransactions() async {
    setState(() {
      _isLoading = true;
      _isMultiSelectMode = false;
      _selectedTransactionIds.clear();
    });
    final transactions = await _firestoreService.getTransactionsForMonth(
      _selectedDate,
    );

    final grouped = <DateTime, List<Transaction>>{};
    final summaries = <DateTime, DailySummary>{};

    for (var txn in transactions) {
      final day = DateTime(txn.date.year, txn.date.month, txn.date.day);
      if (grouped[day] == null) {
        grouped[day] = [];
        summaries[day] = DailySummary();
      }
      grouped[day]!.add(txn);
      if (txn.type == 'Income') {
        summaries[day]!.income += txn.amount;
      } else if (txn.type == 'Expense') {
        summaries[day]!.expense += txn.amount;
      }
    }

    setState(() {
      _groupedTransactions = grouped;
      _dailySummaries = summaries;
      _isLoading = false;
    });
    _calculateTotals(transactions);
  }

  void _calculateTotals(List<Transaction> transactions) {
    double income = 0;
    double expenses = 0;
    double netInvestment = 0;
    for (var txn in transactions) {
      switch (txn.type) {
        case 'Income':
          income += txn.amount;
          break;
        case 'Expense':
          expenses += txn.amount;
          break;
        case 'Investment':
          if (txn.subType == 'Invest / Buy') {
            netInvestment += txn.amount;
          } else if (txn.subType == 'Withdraw / Sell') {
            netInvestment -= txn.amount;
          }
          break;
      }
    }
    setState(() {
      _totalIncome = income;
      _totalExpenses = expenses;
      _netInvestment = netInvestment;
    });
  }

  void _onDateChanged(DateTime newDate) {
    setState(() {
      _selectedDate = newDate;
      _selectedDay = newDate;
    });
    _fetchAndProcessTransactions();
  }

  void _goToPreviousMonth() =>
      _onDateChanged(DateTime(_selectedDate.year, _selectedDate.month - 1));
  void _goToNextMonth() =>
      _onDateChanged(DateTime(_selectedDate.year, _selectedDate.month + 1));

  Future<void> _selectMonth(BuildContext context) async {
    final newDate = await showDialog<DateTime>(
      context: context,
      builder: (BuildContext context) {
        return _CustomMonthPicker(initialDate: _selectedDate);
      },
    );
    if (newDate != null) {
      _onDateChanged(newDate);
    }
  }

  void _toggleMenu({VoidCallback? onClosed}) {
    if (_menuState == MenuState.closed) {
      setState(() => _menuState = MenuState.open);
      _menuController.forward();
    } else {
      _menuController.reverse().whenComplete(() {
        setState(() => _menuState = MenuState.closed);
        onClosed?.call();
      });
    }
  }

  void _navigateAfterMenuCloses(String routeName, {Object? arguments}) {
    _toggleMenu(
      onClosed: () {
        Navigator.pushNamed(context, routeName, arguments: arguments).then((
          result,
        ) {
          if (result == true) {
            _fetchAndProcessTransactions();
          }
        });
      },
    );
  }

  void _onTransactionLongPress(String id) {
    setState(() {
      _isMultiSelectMode = true;
      _selectedTransactionIds.add(id);
    });
  }

  void _onTransactionTap(String id) {
    if (_isMultiSelectMode) {
      setState(() {
        if (_selectedTransactionIds.contains(id)) {
          _selectedTransactionIds.remove(id);
          if (_selectedTransactionIds.isEmpty) {
            _isMultiSelectMode = false;
          }
        } else {
          _selectedTransactionIds.add(id);
        }
      });
    } else {
      Navigator.pushNamed(context, '/edit_transaction', arguments: id).then((
        result,
      ) {
        if (result == true) _fetchAndProcessTransactions();
      });
    }
  }

  void _deleteSelectedTransactions() async {
    final bool? confirm = await showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: Text('Delete ${_selectedTransactionIds.length} Transaction(s)?'),
        content: const Text(
          'This will also update wallet balances and cannot be undone.',
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
      final success = await _firestoreService.deleteTransactions(
        _selectedTransactionIds,
      );
      if (success) {
        _fetchAndProcessTransactions();
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return DefaultTabController(
      length: 5,
      child: Scaffold(
        appBar: _isMultiSelectMode
            ? _buildMultiSelectAppBar()
            : _buildFixedAppBar(),
        body: Stack(
          children: [
            TabBarView(
              // --- THIS IS THE FIX ---
              // The number of children now correctly matches the number of tabs (5).
              children: [
                _buildDailyView(),
                _buildCalendarView(),
                const Center(child: Text('Monthly View')),
                const Center(child: Text('Total View')),
                const Center(child: Text('Note View')),
              ],
            ),
            if (_menuState == MenuState.open)
              GestureDetector(
                onTap: () => _toggleMenu(),
                child: Container(color: Colors.black.withOpacity(0.5)),
              ),
          ],
        ),
        floatingActionButton: _isMultiSelectMode
            ? null
            : _buildFloatingActionButtons(),
      ),
    );
  }

  AppBar _buildFixedAppBar() {
    return AppBar(
      backgroundColor: const Color(0xFF0D256E),
      foregroundColor: Colors.white,
      leading: IconButton(icon: const Icon(Icons.menu), onPressed: () {}),
      title: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          IconButton(
            icon: const Icon(Icons.chevron_left, size: 20),
            onPressed: _goToPreviousMonth,
          ),
          TextButton(
            onPressed: () => _selectMonth(context),
            style: TextButton.styleFrom(foregroundColor: Colors.white),
            child: Text(
              DateFormat('MMM yyyy').format(_selectedDate),
              style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
            ),
          ),
          IconButton(
            icon: const Icon(Icons.chevron_right, size: 20),
            onPressed: _goToNextMonth,
          ),
        ],
      ),
      centerTitle: true,
      actions: [IconButton(icon: const Icon(Icons.search), onPressed: () {})],
      bottom: const TabBar(
        isScrollable: true,
        indicatorColor: Colors.redAccent,
        labelColor: Colors.white,
        unselectedLabelColor: Colors.white70,
        tabs: [
          Tab(text: 'Daily'),
          Tab(text: 'Calendar'),
          Tab(text: 'Monthly'),
          Tab(text: 'Total'),
          Tab(text: 'Note'),
        ],
      ),
    );
  }

  AppBar _buildMultiSelectAppBar() {
    return AppBar(
      backgroundColor: Colors.white,
      foregroundColor: Colors.black,
      leading: IconButton(
        icon: const Icon(Icons.close),
        onPressed: () => setState(() {
          _isMultiSelectMode = false;
          _selectedTransactionIds.clear();
        }),
      ),
      title: Text('${_selectedTransactionIds.length} selected'),
      actions: [
        IconButton(
          icon: const Icon(Icons.delete_outline, color: Colors.red),
          onPressed: _deleteSelectedTransactions,
        ),
      ],
    );
  }

  Widget _buildFloatingActionButtons() {
    final Color primaryColor = Theme.of(context).primaryColor;
    final primaryButtons = [
      _SpeedDialActionButton(
        label: 'Manual Mode',
        icon: Icons.edit,
        onPressed: () => _navigateAfterMenuCloses(
          '/add_transaction',
          arguments: {'type': 'Expense'},
        ),
      ),
      _SpeedDialActionButton(
        label: 'Chat with me',
        icon: Icons.chat_bubble,
        onPressed: () => _navigateAfterMenuCloses('/chat'),
      ),
      _SpeedDialActionButton(
        label: 'Import from Messages',
        icon: Icons.message,
        onPressed: () => _navigateAfterMenuCloses('/import'),
      ),
    ];

    return Column(
      mainAxisSize: MainAxisSize.min,
      crossAxisAlignment: CrossAxisAlignment.end,
      children: [
        if (_menuState == MenuState.open) ...[
          ...List.generate(primaryButtons.length, (index) {
            return AnimatedBuilder(
              animation: _menuController,
              builder: (context, child) {
                final offset =
                    Tween<Offset>(
                      begin: Offset.zero,
                      end: Offset(0, -(index + 1.0) * 10.0),
                    ).animate(
                      CurvedAnimation(
                        parent: _menuController,
                        curve: Curves.easeOut,
                      ),
                    );
                return Transform.translate(
                  offset: offset.value,
                  child: Opacity(
                    opacity: _menuController.value,
                    child: primaryButtons[index],
                  ),
                );
              },
            );
          }).reversed,
        ],
        FloatingActionButton(
          onPressed: () => _toggleMenu(),
          backgroundColor: primaryColor,
          foregroundColor: Colors.white,
          shape: const CircleBorder(),
          child: AnimatedIcon(
            icon: AnimatedIcons.menu_close,
            progress: _menuController,
          ),
        ),
      ],
    );
  }

  Widget _buildDailyView() {
    final currencyFormat = NumberFormat.currency(
      locale: 'en_IN',
      symbol: '₹',
      decimalDigits: 0,
    );

    final filteredGroupedTransactions = Map.fromEntries(
      _groupedTransactions.entries
          .map((entry) {
            if (_activeFilter == 'All') {
              return entry;
            }
            final filteredList = entry.value
                .where((txn) => txn.type == _activeFilter)
                .toList();
            return MapEntry(entry.key, filteredList);
          })
          .where((entry) => entry.value.isNotEmpty),
    );

    final sortedDays = filteredGroupedTransactions.keys.toList()
      ..sort((a, b) => b.compareTo(a));

    return Column(
      children: [
        Container(
          padding: const EdgeInsets.all(16.0),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.spaceAround,
            children: [
              _buildSummaryCard(
                'Income',
                currencyFormat.format(_totalIncome),
                Colors.black87,
                'Income',
              ),
              _buildSummaryCard(
                'Expenses',
                currencyFormat.format(_totalExpenses),
                Colors.red,
                'Expense',
              ),
              _buildSummaryCard(
                'Investment',
                currencyFormat.format(_netInvestment),
                Colors.green,
                'Investment',
              ),
            ],
          ),
        ),
        const Divider(height: 1),
        Expanded(
          child: _isLoading
              ? const Center(child: CircularProgressIndicator())
              : ListView.builder(
                  itemCount: sortedDays.length,
                  itemBuilder: (context, index) {
                    final day = sortedDays[index];
                    final transactionsForDay =
                        filteredGroupedTransactions[day]!;
                    final summary = _dailySummaries[day]!;
                    final isExpanded = _expandedDays.contains(day);

                    return Column(
                      children: [
                        Material(
                          color: Colors.grey[100],
                          child: InkWell(
                            onTap: () {
                              setState(() {
                                if (isExpanded) {
                                  _expandedDays.remove(day);
                                } else {
                                  _expandedDays.add(day);
                                }
                              });
                            },
                            child: Padding(
                              padding: const EdgeInsets.symmetric(
                                horizontal: 16,
                                vertical: 8,
                              ),
                              child: Row(
                                children: [
                                  Text(
                                    DateFormat('dd').format(day),
                                    style: const TextStyle(
                                      fontSize: 24,
                                      fontWeight: FontWeight.bold,
                                    ),
                                  ),
                                  const SizedBox(width: 8),
                                  Text(
                                    DateFormat('EEE\nyyyy').format(day),
                                    style: const TextStyle(color: Colors.grey),
                                  ),
                                  const Spacer(),
                                  Text(
                                    currencyFormat.format(summary.income),
                                    style: const TextStyle(color: Colors.green),
                                  ),
                                  const SizedBox(width: 16),
                                  Text(
                                    currencyFormat.format(summary.expense),
                                    style: const TextStyle(color: Colors.red),
                                  ),
                                  const SizedBox(width: 16),
                                  Icon(
                                    isExpanded
                                        ? Icons.expand_less
                                        : Icons.expand_more,
                                  ),
                                ],
                              ),
                            ),
                          ),
                        ),
                        if (isExpanded)
                          ...transactionsForDay.map((txn) {
                            final isSelected = _selectedTransactionIds.contains(
                              txn.id,
                            );
                            return Slidable(
                              key: ValueKey(txn.id),
                              enabled: !_isMultiSelectMode,
                              startActionPane: ActionPane(
                                motion: const StretchMotion(),
                                children: [
                                  SlidableAction(
                                    onPressed: (context) =>
                                        _onTransactionTap(txn.id),
                                    backgroundColor: Colors.green,
                                    foregroundColor: Colors.white,
                                    icon: Icons.edit,
                                    label: 'Edit',
                                  ),
                                ],
                              ),
                              endActionPane: ActionPane(
                                motion: const StretchMotion(),
                                children: [
                                  SlidableAction(
                                    onPressed: (context) {
                                      _selectedTransactionIds.clear();
                                      _selectedTransactionIds.add(txn.id);
                                      _deleteSelectedTransactions();
                                    },
                                    backgroundColor: Colors.red,
                                    foregroundColor: Colors.white,
                                    icon: Icons.delete,
                                    label: 'Delete',
                                  ),
                                ],
                              ),
                              child: ListTile(
                                onTap: () => _onTransactionTap(txn.id),
                                onLongPress: () =>
                                    _onTransactionLongPress(txn.id),
                                tileColor: isSelected
                                    ? Colors.blue.withOpacity(0.1)
                                    : null,
                                leading: isSelected
                                    ? const Icon(
                                        Icons.check_circle,
                                        color: Colors.blue,
                                      )
                                    : _buildTransactionIcon(txn.category),
                                title: Text(txn.description),
                                subtitle: Text(
                                  '${txn.fromWalletName ?? txn.toWalletName ?? ''} • ${txn.category ?? 'No Category'}',
                                ),
                                trailing: Text(
                                  '${txn.type == 'Income' ? '+' : '-'} ${currencyFormat.format(txn.amount)}',
                                  style: TextStyle(
                                    color: txn.type == 'Income'
                                        ? Colors.green
                                        : Colors.red,
                                    fontWeight: FontWeight.bold,
                                  ),
                                ),
                              ),
                            );
                          }).toList(),
                      ],
                    );
                  },
                ),
        ),
      ],
    );
  }

  Widget _buildCalendarView() {
    final currencyFormat = NumberFormat.currency(
      locale: 'en_IN',
      symbol: '₹',
      decimalDigits: 0,
    );
    final selectedDayTransactions = _groupedTransactions[_selectedDay] ?? [];

    return Column(
      children: [
        TableCalendar(
          firstDay: DateTime.utc(2020, 1, 1),
          lastDay: DateTime.utc(2030, 12, 31),
          focusedDay: _selectedDate,
          calendarFormat: CalendarFormat.month,
          selectedDayPredicate: (day) => isSameDay(_selectedDay, day),
          onDaySelected: (selectedDay, focusedDay) {
            setState(() {
              _selectedDay = selectedDay;
              _selectedDate = focusedDay;
            });
          },
          onPageChanged: (focusedDay) {
            _onDateChanged(focusedDay);
          },
          calendarBuilders: CalendarBuilders(
            markerBuilder: (context, day, events) {
              final summary = _dailySummaries[day];
              if (summary == null) return null;

              return Positioned(
                bottom: 1,
                child: Column(
                  children: [
                    if (summary.income > 0)
                      Text(
                        currencyFormat.format(summary.income),
                        style: const TextStyle(
                          color: Colors.green,
                          fontSize: 10,
                        ),
                      ),
                    if (summary.expense > 0)
                      Text(
                        currencyFormat.format(summary.expense),
                        style: const TextStyle(color: Colors.red, fontSize: 10),
                      ),
                  ],
                ),
              );
            },
          ),
          headerStyle: const HeaderStyle(
            titleCentered: true,
            formatButtonVisible: false,
          ),
        ),
        const Divider(),
        Expanded(
          child: selectedDayTransactions.isEmpty
              ? const Center(child: Text('No transactions on this day.'))
              : ListView.builder(
                  itemCount: selectedDayTransactions.length,
                  itemBuilder: (context, index) {
                    final txn = selectedDayTransactions[index];
                    return ListTile(
                      leading: _buildTransactionIcon(txn.category),
                      title: Text(txn.description),
                      subtitle: Text(
                        '${txn.fromWalletName ?? txn.toWalletName ?? ''} • ${txn.category ?? 'No Category'}',
                      ),
                      trailing: Text(
                        '${txn.type == 'Income' ? '+' : '-'} ${currencyFormat.format(txn.amount)}',
                        style: TextStyle(
                          color: txn.type == 'Income'
                              ? Colors.green
                              : Colors.red,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    );
                  },
                ),
        ),
      ],
    );
  }

  Widget _buildTransactionIcon(String? categoryName) {
    final category = getCategoryDetails(categoryName ?? 'Other');
    return CircleAvatar(
      radius: 20,
      backgroundColor: category.color,
      child: Icon(category.icon, color: Colors.white, size: 20),
    );
  }

  Widget _buildSummaryCard(
    String title,
    String amount,
    Color amountColor,
    String filterType,
  ) {
    final bool isSelected = _activeFilter == filterType;
    return InkWell(
      onTap: () {
        setState(() {
          if (_activeFilter == filterType) {
            _activeFilter = 'All';
          } else {
            _activeFilter = filterType;
          }
        });
      },
      child: Container(
        padding: const EdgeInsets.all(8),
        decoration: BoxDecoration(
          border: isSelected ? Border.all(color: Colors.blue, width: 2) : null,
          borderRadius: BorderRadius.circular(8),
        ),
        child: Column(
          children: [
            Text(
              title,
              style: const TextStyle(color: Colors.grey, fontSize: 16),
            ),
            const SizedBox(height: 4),
            Text(
              amount,
              style: TextStyle(
                color: amountColor,
                fontSize: 18,
                fontWeight: FontWeight.bold,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

//############################################################################
// 3. HELPER WIDGETS
//############################################################################
class _SpeedDialActionButton extends StatelessWidget {
  final String label;
  final IconData icon;
  final VoidCallback onPressed;
  const _SpeedDialActionButton({
    required this.label,
    required this.icon,
    required this.onPressed,
  });

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onPressed,
      splashColor: Colors.white.withOpacity(0.2),
      borderRadius: BorderRadius.circular(8),
      child: Container(
        margin: const EdgeInsets.only(bottom: 10, right: 8),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              padding: const EdgeInsets.symmetric(vertical: 6, horizontal: 12),
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(8),
                boxShadow: [
                  BoxShadow(
                    color: Colors.black.withOpacity(0.1),
                    blurRadius: 4,
                    offset: const Offset(0, 2),
                  ),
                ],
              ),
              child: Text(
                label,
                style: const TextStyle(fontWeight: FontWeight.bold),
              ),
            ),
            const SizedBox(width: 12),
            FloatingActionButton.small(
              onPressed: null,
              backgroundColor: Colors.white,
              foregroundColor: Theme.of(context).primaryColor,
              heroTag: null,
              child: Icon(icon),
            ),
          ],
        ),
      ),
    );
  }
}

class _CustomMonthPicker extends StatefulWidget {
  final DateTime initialDate;
  const _CustomMonthPicker({required this.initialDate});

  @override
  State<_CustomMonthPicker> createState() => _CustomMonthPickerState();
}

class _CustomMonthPickerState extends State<_CustomMonthPicker> {
  late int selectedYear;
  late int? selectedMonth;

  @override
  void initState() {
    super.initState();
    selectedYear = widget.initialDate.year;
    selectedMonth = widget.initialDate.month;
  }

  @override
  Widget build(BuildContext context) {
    const months = [
      'Jan',
      'Feb',
      'Mar',
      'Apr',
      'May',
      'Jun',
      'Jul',
      'Aug',
      'Sep',
      'Oct',
      'Nov',
      'Dec',
    ];
    return AlertDialog(
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      contentPadding: EdgeInsets.zero,
      content: SizedBox(
        width: double.maxFinite,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
              decoration: const BoxDecoration(
                color: Color(0xFF0D256E),
                borderRadius: BorderRadius.only(
                  topLeft: Radius.circular(12),
                  topRight: Radius.circular(12),
                ),
              ),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  IconButton(
                    icon: const Icon(Icons.chevron_left, color: Colors.white),
                    onPressed: () => setState(() => selectedYear--),
                  ),
                  Text(
                    selectedYear.toString(),
                    style: const TextStyle(
                      color: Colors.white,
                      fontSize: 18,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  IconButton(
                    icon: const Icon(Icons.chevron_right, color: Colors.white),
                    onPressed: () => setState(() => selectedYear++),
                  ),
                ],
              ),
            ),
            Padding(
              padding: const EdgeInsets.all(16.0),
              child: GridView.builder(
                shrinkWrap: true,
                physics: const NeverScrollableScrollPhysics(),
                gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                  crossAxisCount: 4,
                  childAspectRatio: 1.5,
                ),
                itemCount: months.length,
                itemBuilder: (context, index) {
                  final month = index + 1;
                  final isSelected = month == selectedMonth;
                  return TextButton(
                    style: TextButton.styleFrom(
                      backgroundColor: isSelected
                          ? Colors.blue.withOpacity(0.1)
                          : null,
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(8),
                      ),
                    ),
                    onPressed: () => setState(() => selectedMonth = month),
                    child: Text(months[index]),
                  );
                },
              ),
            ),
            Padding(
              padding: const EdgeInsets.only(right: 16, bottom: 16),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.end,
                children: [
                  TextButton(
                    onPressed: () => Navigator.of(context).pop(),
                    child: const Text('CANCEL'),
                  ),
                  const SizedBox(width: 8),
                  TextButton(
                    onPressed: () {
                      if (selectedMonth != null) {
                        Navigator.of(
                          context,
                        ).pop(DateTime(selectedYear, selectedMonth!));
                      }
                    },
                    child: const Text('OK'),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

// A simple reusable AppBar for the placeholder screens
class _CustomAppBar extends StatelessWidget implements PreferredSizeWidget {
  final String title;
  const _CustomAppBar({required this.title});

  @override
  Widget build(BuildContext context) {
    return AppBar(
      title: Text(title),
      backgroundColor: const Color(0xFF0D256E),
      foregroundColor: Colors.white,
      automaticallyImplyLeading: false,
    );
  }

  @override
  Size get preferredSize => const Size.fromHeight(kToolbarHeight);
}
