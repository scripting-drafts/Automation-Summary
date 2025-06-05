import java.awt.*;
import java.util.Random;

public class GeneralPurposeClicker {
    public static void main(String[] args) throws AWTException, InterruptedException {
        // Define the coordinates to click
        int[][] coordinates = {
            {500, 300},
            {600, 400},
            {700, 500}
        };

        // Number of times to repeat the clicking sequence
        int timesToRepeat = 10;

        // Create a Robot instance for simulating mouse events
        Robot robot = new Robot();
        Random random = new Random();

        for (int i = 0; i < timesToRepeat; i++) {
            for (int[] coord : coordinates) {
                int x = coord[0];
                int y = coord[1];

                // Move the mouse to the specified coordinates
                robot.mouseMove(x, y);

                // Simulate mouse press and release (left-click)
                robot.mousePress(InputEvent.BUTTON1_DOWN_MASK);
                robot.mouseRelease(InputEvent.BUTTON1_DOWN_MASK);

                // Wait for a random duration between 500ms to 1500ms
                int delay = 500 + random.nextInt(1000);
                Thread.sleep(delay);
            }
        }
    }
}