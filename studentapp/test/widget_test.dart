import 'package:flutter_test/flutter_test.dart';
import 'package:studentapp/main.dart';

void main() {
  testWidgets('App renders', (WidgetTester tester) async {
    await tester.pumpWidget(const MarkinApp());
    expect(find.text('MARKIN'), findsOneWidget);
  });
}
