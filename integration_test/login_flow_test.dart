import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:money_bhai/main.dart'
    as app; // Import your app's main entry point

void main() {
  // This ensures that the IntegrationTestWidgetsFlutterBinding is initialized.
  // It's a required setup step.
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();

  // A group of related tests for the login flow.
  group('Login Flow Tests', () {
    // TEST CASE 1: User provides incorrect credentials and sees an error dialog.
    testWidgets('Shows error dialog on failed login', (
      WidgetTester tester,
    ) async {
      // Start the app.
      app.main();

      // Allow the app to finish loading and building its widgets.
      await tester.pumpAndSettle();

      // Find the username/email and password text fields.
      final identifierField = find.widgetWithText(
        TextFormField,
        'Username, Email or Phone Number',
      );
      final passwordField = find.widgetWithText(TextFormField, 'Password');
      final loginButton = find.widgetWithText(ElevatedButton, 'Log In');

      // Verify that all the necessary widgets are on the screen.
      expect(identifierField, findsOneWidget);
      expect(passwordField, findsOneWidget);
      expect(loginButton, findsOneWidget);

      // Enter incorrect credentials into the fields.
      await tester.enterText(identifierField, 'wronguser');
      await tester.enterText(passwordField, 'wrongpassword');

      // Tap the "Log In" button.
      await tester.tap(loginButton);

      // Wait for the app to process the login and update the UI.
      // We use pump() for single frames and pumpAndSettle() to wait for all animations to finish.
      await tester.pump(
        const Duration(seconds: 1),
      ); // Wait for the loading indicator
      await tester.pumpAndSettle(); // Wait for the dialog to appear

      // VERIFY THE OUTCOME:
      // 1. Check that the error dialog is now visible.
      expect(find.byType(AlertDialog), findsOneWidget);

      // 2. Check for the specific error message you wanted.
      expect(
        find.text(
          'You are still not part of the Money Bhai Family. Please continue with sign up.',
        ),
        findsOneWidget,
      );

      // 3. Check that the "Sign Up" button is in the dialog.
      final signUpButtonInDialog = find.widgetWithText(
        ElevatedButton,
        'Sign Up',
      );
      expect(signUpButtonInDialog, findsOneWidget);

      // Tap the sign up button in the dialog.
      await tester.tap(signUpButtonInDialog);
      await tester.pumpAndSettle();

      // 4. Verify that we have navigated to the SignUpScreen.
      expect(find.text("Let's create an account"), findsOneWidget);
    });

    // TEST CASE 2: User provides correct credentials and navigates to the home screen.
    testWidgets('Navigates to home screen on successful login', (
      WidgetTester tester,
    ) async {
      // Start the app.
      app.main();
      await tester.pumpAndSettle();

      // Find the widgets on the login screen.
      final identifierField = find.widgetWithText(
        TextFormField,
        'Username, Email or Phone Number',
      );
      final passwordField = find.widgetWithText(TextFormField, 'Password');
      final loginButton = find.widgetWithText(ElevatedButton, 'Log In');

      // Enter the CORRECT credentials from your mock database.
      await tester.enterText(identifierField, 'testuser');
      await tester.enterText(passwordField, 'password123');

      // Tap the "Log In" button.
      await tester.tap(loginButton);

      // Wait for the login process and navigation to complete.
      await tester.pump(const Duration(seconds: 1));
      await tester.pumpAndSettle();

      // VERIFY THE OUTCOME:
      // 1. Check that the login screen is no longer visible.
      expect(find.text('Hi !\nWelcome'), findsNothing);

      // 2. Check that the HomeScreen is now visible by looking for a unique widget from that screen,
      // for example, the app bar title.
      expect(find.text('Aug 2025'), findsOneWidget);
      expect(find.byType(BottomNavigationBar), findsOneWidget);
    });
  });
}
