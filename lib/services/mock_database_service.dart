/// A dummy user model.
class User {
  final String username;
  final String password;
  final String email;

  User({required this.username, required this.password, required this.email});
}

/// This class simulates a real database to test our login logic.
/// Later, you can replace the logic inside these methods to call a real
/// database like Firebase or your own backend server.
class MockDatabaseService {
  // A list of dummy users who are already "signed up".
  // For testing, you can log in with:
  // username: testuser
  // password: password123
  final List<User> _users = [
    User(
      username: 'testuser',
      password: 'password123',
      email: 'test@example.com',
    ),
    User(username: 'mrigank', password: 'flutterdev', email: 'mrigank@dev.com'),
  ];

  /// Simulates a network call to check if a user exists and the password is correct.
  Future<bool> loginUser(String identifier, String password) async {
    // Simulate a 1-second network delay to feel more realistic.
    await Future.delayed(const Duration(seconds: 1));

    try {
      // Find a user where the username or email matches the identifier.
      final user = _users.firstWhere(
        (user) => user.username == identifier || user.email == identifier,
      );

      // If a user is found, check if the password matches.
      return user.password == password;
    } catch (e) {
      // 'firstWhere' throws an error if no element is found, which means the user doesn't exist.
      return false;
    }
  }
}
