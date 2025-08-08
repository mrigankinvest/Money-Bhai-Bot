import 'package:firebase_auth/firebase_auth.dart';
import 'package:cloud_firestore/cloud_firestore.dart';
import 'firestore_service.dart';

/// A service class to handle all Firebase Authentication and Firestore user operations.
class FirebaseAuthService {
  // Get instances of Firebase Auth and Firestore to use throughout the class.
  final FirebaseAuth _auth = FirebaseAuth.instance;
  final FirebaseFirestore _firestore = FirebaseFirestore.instance;
  final FirestoreService _firestoreService = FirestoreService();

  /// Signs up a new user with email and password, and saves their details to Firestore.
  ///
  /// Takes [email], [password], [fullName], and [username] as input.
  /// Returns a [User] object on success, or `null` on failure.
  Future<User?> signUpWithEmailAndPassword(
    String email,
    String password,
    String fullName,
    String username,
  ) async {
    try {
      // Step 1: Create the user in Firebase Authentication.
      // This handles the secure storage of the user's email and password.
      UserCredential credential = await _auth.createUserWithEmailAndPassword(
        email: email,
        password: password,
      );
      User? user = credential.user;

      // Step 2: If the user was created successfully, save their additional details.
      if (user != null) {
        // We create a new document in the 'users' collection.
        // The document's ID is the user's unique ID (uid) from Firebase Auth.
        // This links the auth record to the database record.
        await _firestore.collection('users').doc(user.uid).set({
          'fullName': fullName,
          'username': username,
          'email': email,
          'createdAt': Timestamp.now(), // Store the sign-up date.
        });

        await _firestoreService.addDefaultWallet(user.uid);
      }
      return user;
    } on FirebaseAuthException catch (e) {
      // This catches specific errors from Firebase Authentication, like
      // 'email-already-in-use' or 'weak-password'.
      print("Firebase Auth Error: ${e.message}");
      return null;
    } catch (e) {
      // This catches any other unexpected errors during the process.
      print("An unexpected error occurred: $e");
      return null;
    }
  }

  /// Signs in an existing user with their email and password.
  ///
  /// Takes [email] and [password] as input.
  /// Returns a [User] object on success, or `null` on failure.
  Future<User?> signInWithEmailAndPassword(
    String email,
    String password,
  ) async {
    try {
      // Attempt to sign in with the provided credentials.
      UserCredential credential = await _auth.signInWithEmailAndPassword(
        email: email,
        password: password,
      );
      return credential.user;
    } on FirebaseAuthException catch (e) {
      // Catches specific sign-in errors like 'user-not-found' or 'wrong-password'.
      print("Firebase Auth Error: ${e.message}");
      return null;
    } catch (e) {
      print("An unexpected error occurred: $e");
      return null;
    }
  }

  /// Signs out the current user.
  Future<void> signOut() async {
    await _auth.signOut();
  }
}
