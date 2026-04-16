#include <stdio.h>                                                      // For printf and related C-style I/O functions
#include <iostream>                                                     // For std::cout and std::endl for C++ style I/O
#include <vector>                                                       // For std::vector from the C++ Standard Library, which can be useful for managing dynamic arrays of data if needed in future expansions of the code
#include "pubSysCls.h"                                                  // For SysManager and related classes from ClearView's C++ API (motor code)
#include <unistd.h>                                                     // Required for usleep, which is used for adding delays in the code. This is a POSIX function and is commonly used in C and C++ programs running on Unix-like operating systems.

using namespace sFnd;                                                   // For SysManager and related classes from ClearView's C++ API

// Globals so multiple functions can use them
static SysManager* g_mgr = nullptr;                                     // Global pointer to the system manager (assumes only one system manager instance for simplicity)
static INode*      g_node = nullptr;                                    // Global pointer to the motor node (assumes only one motor for simplicity)

// Helper declarations
void msgUser(const char* msg);                                          // Simple helper to print a message and wait for user input
void printNodeInfo(INode& node);                                        // Helper to print some info about a node
bool moveAtVelocity(INode&, int);                                       // Helper to execute a velocity move and wait for it to reach target speed
bool moveDistance(INode& node, int target, bool targetIsAbsolute);      // Helper to execute a position move and wait for it to complete

//--------------------------------------------------------------------------------------------------------------setup_and_home()----------------------------------------------------------------------------------------------------------------------//
// Exported: initialize system and node
                                                                                                                // Note: extern "C" allows the function to be called from C code or other languages that use C calling conventions, which can be useful for integration with various applications and scripting languages.
extern "C" int setup_and_home(int timeout_ms) {                                                                 // This function ensures the homing sequence is executed immediately after setup without any user intervention that could cause timing issues.
    printf("Initializing System and Starting Hardware-Controlled Homing...\n");             
    
    try {                                                                                                       // Use a try/catch block to handle any exceptions that might be thrown during setup and homing
        g_mgr = SysManager::Instance();                                                                         // Get the singleton instance of the system manager, which is responsible for managing communication with the motor and hub. This is necessary to perform any operations with the motor, including setup, homing, and motion commands. By using a global pointer, we can access the system manager from other functions as needed.
        
        // 1. Port Initialization
        g_mgr->PortsClose();                                                                                    // Close any existing connections to clear the port
        g_mgr->ComHubPort(0, "/dev/ttyXRUSB0");                                                                 // Define the port - use Net 0 and the path we verified
        
        try {                                                                                                   // Open the port. We use a try/catch here in case the OS has it locked.
            g_mgr->PortsOpen(1);                                                                                // Try to open the port
        } catch (mnErr& e) {                                                                                    // If it fails, print the error and retry once after a short delay
            printf("Port open failed: %s. Retrying...\n", e.ErrorMsg);
            usleep(500000);                                                                                     // Wait 0.5s before retrying
            g_mgr->PortsOpen(1);                                                                                // Retry opening the port after a short delay
        }

        IPort& port = g_mgr->Ports(0);                                                                          // Get a reference to the port we just opened
        int retry = 0;                                                                                          // Wait for the SC-Hub to find the motor nodes. This is a common failure point on Raspberry Pi, so we wait and retry for a reasonable amount of time (e.g., 3 seconds total).
        while (port.NodeCount() == 0 && retry < 30) {                                                           // Check if any nodes are detected, if not wait and retry
            usleep(100000);                                                                                     // Wait 100ms
            retry++;                                                                                            // Increment retry counter
        } 

        if (port.NodeCount() == 0) {                                                                            // If after waiting and retrying no nodes are detected, print an error and exit
            printf("Error: No motors detected on /dev/ttyXRUSB0\n");
            return 1;                                                                                           // Exit with error code
        }

        // 2. Node Preparation
        g_node = &port.Nodes(0);                                                                                // Get a reference to the first node (assuming only one motor for simplicity) if more motors are present, additional logic would be needed to select the correct one
        g_node->Status.AlertsClear();                                                                           // Clear any existing alerts that might prevent the motor from enabling
        g_node->Motion.NodeStopClear();                                                                         // Clear any existing node stops that might prevent the motor from enabling   
        g_node->EnableReq(true);                                                                                // Send the enable request to the motor to power it on and prepare it for motion commands

        // Wait for motor to enable (max 5s)
        double enableTimeout = g_mgr->TimeStampMsec() + 5000;                                                   // Set a timeout for enabling the motor to avoid waiting indefinitely if something goes wrong. We check if the motor is ready to receive motion commands, which indicates it has successfully enabled.     
        while (!g_node->Motion.IsReady()) {                                                                     // Wait for the motor to report that it is ready to receive motion commands, which indicates it has successfully enabled. We also check for a timeout to avoid waiting indefinitely if something goes wrong.      
            if (g_mgr->TimeStampMsec() > enableTimeout) {                                                       // If the motor is not ready within the timeout period, print an error and exit
                printf("Error: Motor failed to enable.\n");
                return 1;                                                                                       // Exit with error code 
            }
            usleep(1000);                                                                                       // Wait 1ms before checking again to prevent 100% CPU usage while waiting for the motor to enable
        }

        // 3. Homing Sequence 
        // Motor uses settings (including Offset) saved in its Flash via ClearView
        if (!g_node->Motion.Homing.HomingValid()) {                                                             // Before initiating homing, check if the homing parameters are valid. If not, print an error and exit. This prevents starting a homing sequence that is guaranteed to fail due to missing or invalid configuration. 
            printf("Error: Homing not configured/valid in motor flash.\n");
            return 1;                                                                                           // Exit with error code
        }

        printf("Node found: %s. Initiating Homing Sequence...\n", g_node->Info.UserID.Value()); 
        g_node->Motion.Homing.Initiate();                                                                       // Initiate the homing sequence. The motor will automatically move to the hardstop and then to the offset position defined in its flash memory. We do not need to manually command it to move to the offset; it is part of the homing sequence as configured in ClearView.

        // The motor will hit the hardstop and then move to its offset automatically.
        // WasHomed() only turns true AFTER the offset move is complete.
        double homingTimeout = g_mgr->TimeStampMsec() + timeout_ms;                                             // Set a timeout for the homing process to avoid waiting indefinitely if something goes wrong. The homing sequence should complete within a reasonable time frame (e.g., 10 seconds), so we check for a timeout to handle cases where the motor might be stalled or an alert is triggered during homing.
        while (!g_node->Motion.Homing.WasHomed()) {                                                              
            g_node->Status.RT.Refresh();                                                                        // During homing, continuously check for alerts and the timeout condition. If an alert is triggered or if the homing process takes too long, print an error, disable the motor for safety, and exit. This ensures that we do not leave the motor enabled in a potentially unsafe state if homing fails.
            if (g_node->Status.RT.Value().cpm.AlertPresent || g_mgr->TimeStampMsec() > homingTimeout) {         // If an alert is triggered during homing or if the homing process takes too long (indicating a potential issue), print an error, disable the motor for safety, and exit. This ensures that we do not leave the motor enabled in a potentially unsafe state if homing fails.
                printf("Homing failed: Alert triggered or Timeout reached.\n");
                g_node->EnableReq(false);                                                                       // If homing fails due to an alert or timeout, disable the motor for safety
                return 1;                                                                                       // Exit with error code if homing fails due to an alert or timeout
            }
            usleep(1000);                                                                                       // Wait 1ms before checking again to prevent 100% CPU usage while waiting for homing to complete
        }

        // 4. Force Position to Zero and Signal Complete
        // Refresh the position after the hardware move to the offset is done
        g_node->Motion.PosnMeasured.Refresh();                                                                  // After homing is complete, the motor's internal position register will be at the offset value defined in ClearView. To force the current position to be treated as zero, we can take the current measured position and subtract it from itself, which effectively applies an offset that makes the current position read as zero. This allows us to use absolute moves relative to this new zero point without needing to change the motor's flash configuration or perform an additional move command.
        
        // Take the current internal count and subtract it from itself
        // to force the motor's internal register to exactly 0.
        double currentPos = g_node->Motion.PosnMeasured.Value();                                                // Read the current measured position, which should be at the offset after homing. We will use this value to apply an offset that forces the current position to be treated as zero.
        g_node->Motion.AddToPosition(-currentPos);                                                              // Apply an offset equal to the negative of the current position, which effectively forces the motor's internal position register to read as zero. This allows us to use absolute moves relative to this new zero point without needing to change the motor's flash configuration or perform an additional move command.
        
        // Now signal that homing is complete at this new 0 point
        g_node->Motion.Homing.SignalComplete();                                                                 // Signal that homing is complete. This is important because some functions may check the homing status before allowing certain moves. By signaling that homing is complete, we ensure that the system recognizes that we have a valid home position (even though we applied an offset to make it zero) and allows us to execute moves based on this new reference point.

        printf("Setup and Homing complete. Position forced to 0 (Offset applied).\n");
        return 0;                                                                                               // Exit with success code                               

    } catch (mnErr& e) {                                                                                        // Catch any errors that occur during setup or homing and print the error message. This will help with debugging if something goes wrong during initialization or homing.
        printf("Setup/Homing Error: %s\n", e.ErrorMsg);
        return 1;                                                                                               // Exit with error code if an exception is caught during setup or homing     
    } catch (...) {                                                                                             // Catch any other unexpected exceptions that are not of type mnErr and print a generic error message. This is a safety net to catch any unforeseen issues that might arise during setup or homing, ensuring that we provide some feedback rather than crashing silently.
        printf("Unknown error during setup/homing.\n");
        return 1;                                                                                               // Exit with error code if an unknown exception is caught during setup or homing
    }
}

//--------------------------------------------------------------------------------------------------------------setup_and_home() end------------------------------------------------------------------------------------------------------------------//

//-------------------------------------------------------------------------------------acceleration_velocity_set()------------------------------------------------------------------------------------------------------------------//

// Exported: set acceleration and velocity limits
extern "C" int acceleration_velocity_set(int acceleration, int velocity) {             // Set acceleration and velocity limits in a single function, which ensures that both parameters are updated together without requiring multiple calls from the user.
    if (!g_node) {                                                                     // Check if the node is initialized before trying to set parameters. If not, print an error and exit. This prevents trying to access a null pointer if the user forgets to call setup_and_home() first.
        printf("Node not initialized. Call setup_and_home() first.\n");
        return 1;
    }

    g_node->AccUnit(INode::RPM_PER_SEC);                                               // Set the acceleration unit to RPM/s. This ensures that the acceleration value we set is interpreted correctly by the motor.
    g_node->VelUnit(INode::RPM);                                                       // Set the velocity unit to RPM. This ensures that the velocity value we set is interpreted correctly by the motor.
    g_node->Motion.AccLimit = acceleration;                                            // Set the acceleration limit to the value provided by the user. This will limit how quickly the motor can accelerate, which can help prevent mechanical stress and ensure smoother motion.
    g_node->Motion.VelLimit = velocity;                                                // Set the velocity limit to the value provided by the user. This will limit the maximum speed of the motor, which can be important for safety and to prevent overshooting targets.

    printf("Set AccLimit=%d rpm/s, VelLimit=%d rpm\n", acceleration, velocity);
    return 0;                                                                          // Exit with success code after setting the parameters successfully
}

//-------------------------------------------------------------------------------------acceleration_velocity_set() end------------------------------------------------------------------------------------------------------------------//

//------------------------------------------------------------------------------move_speed() and move_counts()------------------------------------------------------------------------------------------------------------------//

// Exported: Move at specified velocity
extern "C" int move_speed(int target) {                                         // Updated to a more descriptive name and to check for node initialization before attempting to move. This function will ramp the motor up to the specified target velocity and wait until it reaches that velocity, while also checking for alerts and timeouts during the ramp-up process.
    if (!g_node) {                                                              // Check if the node is initialized before trying to move. If not, print an error and exit. This prevents trying to access a null pointer if the user forgets to call setup_and_home() first.
        // Updated to match your new combined function name
        printf("Node not initialized. Call setup_and_home() first.\n");
        return 1;
    }
    
    bool ok = moveAtVelocity(*g_node, target);                                  // Call the helper function to execute the velocity move and wait for it to reach the target speed. The helper function will handle checking if the node is ready, executing the move, and monitoring for alerts and timeouts during the ramp-up process. 
    return ok ? 0 : 1;                                                          // We return 0 if the move was successful and 1 if it failed for any reason (e.g., node not ready, alert triggered, timeout reached).
}

// Exported: perform a move
extern "C" int move_counts(int target, int isAbsolute) {                        // This function will execute a position move to the specified target counts, either as an absolute position or as a relative move based on the isAbsolute flag. It will wait for the move to complete and check for alerts during the move.
    if (!g_node) {                                                              // Check if the node is initialized before trying to move. If not, print an error and exit. This prevents trying to access a null pointer if the user forgets to call setup_and_home() first.
        printf("Node not initialized. Call setup_and_home() first.\n");
        return 1;
    }

    bool ok = moveDistance(*g_node, target, isAbsolute != 0);                   // Call the helper function to execute the position move and wait for it to complete. The helper function will handle checking if the node is ready, executing the move, and monitoring for alerts during the move. The isAbsolute parameter is converted to a boolean by checking if it is not equal to zero.
    return ok ? 0 : 1;                                                          // We return 0 if the move was successful and 1 if it failed for any reason (e.g., node not ready, alert triggered during the move).         
}

//------------------------------------------------------------------------------move_speed and move_counts() end------------------------------------------------------------------------------------------------------------------//

//--------------------------------------shutdown_node()--------------------------------------------------------------------------------------------------------------------------------------------//

// Exported: shutdown   
extern "C" void shutdown_node() {       // Ensures that we check if the node and manager are initialized before trying to access them. This function will disable the motor and close the port, ensuring a clean shutdown of the system.
    if (g_node) {                       // Check if the motor node is initialized before trying to disable it.  
        g_node->EnableReq(false);       // If it is, disable the motor to ensure it is not left enabled, which could be a safety hazard. This will also help prevent issues with the motor being enabled when we try to initialize it again later without a full system reset.
    }
    if (g_mgr) {                        // Check if the system manager is initialized before trying to close the port. 
        g_mgr->PortsClose();            // If it is, close the port to clean up resources and ensure that the system is in a known state for the next time it is initialized. This is important for preventing issues with locked ports or residual states in the motor or hub.
}

//--------------------------------------shutdown_node() end---------------------------------------------------------------------------------------------------------------------------------------------------------------------//

//-------------------------------------------------------------------------------------helpers------------------------------------------------------------------------------------------------------------------//

// --- helpers from your original code ---
void msgUser(const char* msg) {     // Simple helper to print a message and wait for user input
    std::cout << msg;               // Print the message to the console
    getchar();                      // Wait for the user to press Enter before continuing. This is useful for pausing the program at certain points to allow the user to read messages or prepare for the next step.
}

void printNodeInfo(INode& node) {                                                       // Helper to print some info about a node. This can be useful for debugging and verifying that we are communicating with the correct motor and that it has the expected configuration.
    printf("   Node[%d]: type=%d\n", node.Info.Ex.NodeIndex(), node.Info.NodeType());   // Print the node index and type. This helps us identify which node we are working with, especially if there are multiple nodes present.
    printf("            userID: %s\n", node.Info.UserID.Value());                       // Print the user ID of the node, which is a customizable string that can be set in ClearView. This can help us identify the motor and confirm that we are communicating with the correct one.
    printf("        FW version: %s\n", node.Info.FirmwareVersion.Value());              // Print the firmware version of the motor, which can be important for compatibility and debugging purposes. Different firmware versions may have different features or behaviors, so it's useful to know which version is running on the motor.
    printf("          Serial #: %d\n", node.Info.SerialNumber.Value());                 // Print the serial number of the motor, which is a unique identifier for each motor. This can be useful for inventory management, support, and ensuring that we are working with the correct hardware.
    printf("             Model: %s\n", node.Info.Model.Value());                        // Print the model of the motor, which can provide information about its capabilities, specifications, and intended applications. This can help us understand the performance characteristics of the motor we are working with and ensure that it meets our requirements for the application.
}

bool moveDistance(INode& node, int target, bool targetIsAbsolute) {                             // we can't execute a move unless the node is ready to receive motion commands 
    if (!node.Motion.IsReady()) {
        printf("Node[%d]: Move cancelled; node not ready\n", node.Info.Ex.NodeIndex());         // If the node is not ready to receive motion commands, print a message indicating that the move is cancelled and return false. This can happen if the motor is still enabling, if there is an alert that has not been cleared, or if there is a node stop condition that has not been cleared. By checking this before attempting to execute the move, we can avoid trying to command a move that is guaranteed to fail and provide clearer feedback about why the move cannot be executed.
        return false;
    }

    node.Status.Rise.Refresh();                                                                 // Refresh then Clear the rising register before starting the move so that we can detect events that occurred during the move.
    node.Status.Rise.Clear();                                                                   // This ensures that any alerts or events that occur during the move will be captured in the Rising register, allowing us to check for them after the move completes.

    printf("Node[%d]: Moving %d counts, isAbsolute=%d\n",
           node.Info.Ex.NodeIndex(), target, targetIsAbsolute);                                 // Print the target position and whether it is an absolute or relative move. This provides feedback to the user about the move that is being executed, which can be helpful for debugging and understanding the behavior of the system.
    node.Motion.MovePosnStart(target, targetIsAbsolute);                                        // Execute the position move. The targetIsAbsolute flag determines whether the target position is treated as an absolute position (relative to the home position) or as a relative move (relative to the current position). This allows for flexibility in commanding moves based on different reference points.
    double est = node.Motion.MovePosnDurationMsec(target, targetIsAbsolute);                    // Estimate the duration of the move in milliseconds based on the target position and whether it is absolute or relative. This can provide feedback to the user about how long the move is expected to take, which can be useful for timing and synchronization in applications where multiple moves or actions are coordinated.
    printf("%.2f ms estimated.\n", est);    

    while (!node.Motion.MoveIsDone());                                                          // Wait for the move to complete. MoveIsDone() will return true when the move has completed successfully or if it was interrupted by a shutdown. We want to wait until the move is done before checking for alerts or other events that might have occurred during the move.

    mnStatusReg mask;                                                                           // Create a status register mask to test the Rising register for relevant events that could indicate a problem during the move. We want to check for any alerts that might have been triggered, as well as if the move was canceled for any reason.
    mask.cpm.AlertPresent = 1;                                                                  // Set AlertPresent bit to check if any alert was triggered during the move, which could indicate an issue such as an overcurrent, stall, or other fault condition that occurred while trying to execute the move.
    mask.cpm.MoveCanceled = 1;                                                                  // Set MoveCanceled bit to check if the move was canceled, which could happen if the motor was disabled, if a node stop was triggered, or if another command interrupted the move. This helps us determine if the failure to complete the move was due to an external interruption rather than an alert condition.

    mnStatusReg result;                                                                         // Store results from testing the Rising register. This will allow us to determine if any of the conditions we were checking for (alerts or move cancellation) occurred during the move, which helps us understand why the move might not have completed successfully.  
    if (node.Status.Rise.TestAndClear(mask, result)) {              
        if (result.cpm.AlertPresent)                                                            // If the AlertPresent bit is set, it indicates that an alert was triggered during the move, which could indicate a fault condition such as an overcurrent, stall, or other issue that occurred while trying to execute the move. This is important to check because it helps us understand if the move did not complete successfully due to a problem with the motor or the conditions of the move, rather than just an external interruption. By checking this bit, we can provide more specific feedback about why the move failed and take appropriate actions if needed (e.g., investigating the cause of the alert, clearing alerts, etc.).
            printf("Move failed: AlertPresent\n");
        if (result.cpm.MoveCanceled)                                                            // If the MoveCanceled bit is set, it indicates that the move was canceled, which could happen for various reasons such as the motor being disabled during the move, a node stop command being issued, or another command interrupting the move. This is important to check because it helps us understand if the move did not complete successfully due to an external interruption rather than an alert condition. By checking this bit, we can provide more specific feedback about why the move failed and take appropriate actions if needed (e.g., re-enabling the motor, clearing node stops, etc.).
            printf("Move failed: MoveCanceled\n");
        return false;                                                                           // Move did not complete successfully due to an alert or cancellation
    }

    printf("Node[%d]: Move Done\n", node.Info.Ex.NodeIndex());                                  // If we reach this point, the move completed successfully and we did not detect any alerts or cancellations during the move. We can print a message indicating that the move is done and return true to indicate success.
    return true;                                                    
}

bool moveAtVelocity(INode& node, int target) {                                              // This function will ramp the motor up to the specified target velocity and wait until it reaches that velocity, while monitoring for any issues that might arise during the ramp-up.
    // we can't execute a move unless the node is ready to receive motion commands
    if (!node.Motion.IsReady()) {                                                           // If the node is not ready to receive motion commands, print a message indicating that the move is cancelled and return false. This can happen if the motor is still enabling, if there is an alert that has not been cleared, or if there is a node stop condition that has not been cleared. By checking this before attempting to execute the move, we can avoid trying to command a move that is guaranteed to fail and provide clearer feedback about why the move cannot be executed.
        printf("Node[%d]: Move canceled. Node not ready.\n", node.Info.Ex.NodeIndex());
        return false;                                                                       
    }

    // Refresh then Clear the rising register before starting the move so that we can detect events that occurred during the move.
    node.Status.Rise.Refresh();            
    node.Status.Rise.Clear();

    printf("Node[%d]: Ramping to velocity %d RPM...\n", node.Info.Ex.NodeIndex(), target);
    node.Motion.MoveVelStart(target);                                               // Execute velocity move

    // Set a safety timeout (e.g., 5 seconds to reach target speed)
    double timeoutTime = g_mgr->TimeStampMsec() + 5000;                             // We set a timeout for reaching the target velocity to avoid waiting indefinitely if something goes wrong during the ramp-up process, such as the motor stalling, incorrect parameters, or an alert condition that prevents the motor from reaching the target speed. By checking for a timeout, we can provide feedback about the failure and take appropriate actions (e.g., stopping the motor) rather than getting stuck in an infinite loop waiting for a condition that may never be met.

    // Wait for the node to reach its target velocity
    // Note: VelocityAtTarget() will return true when the motor has reached the target velocity within a certain tolerance. 
    //We also check for a timeout to avoid waiting indefinitely if something goes wrong (e.g., motor stalled, incorrect parameters, etc.).
    while (!node.Motion.VelocityAtTarget()) {                                                                                 
        if (g_mgr->TimeStampMsec() > timeoutTime) {                                  // If we fail to reach the target velocity within the timeout period, we print an error message and stop the motor to prevent it from continuing to try to ramp up indefinitely, which could potentially cause damage or unsafe conditions. We then return false to indicate that we did not successfully reach the target velocity.
            printf("Node[%d]: Error - Failed to reach target velocity (Timeout).\n", node.Info.Ex.NodeIndex());
            node.Motion.NodeStop(STOP_TYPE_ABRUPT);                                                                            
            return false;
        }
        usleep(1000); // Prevent 100% CPU usage
    }

    // Check for alerts during the ramp-up
    mnStatusReg mask;                                   // Create a status register mask to test the Rising register for relevant events that could indicate a problem during the velocity ramp-up. We want to check for any alerts that might have been triggered, as well as if the move was canceled for any reason.
    mask.cpm.AlertPresent = 1;                          // Set AlertPresent bit to check if any alert was triggered during the move, which could indicate an issue such as an overcurrent, stall, or other fault condition that occurred while trying to reach the target velocity.
    mask.cpm.MoveCanceled = 1;                          // Set MoveCanceled bit to check if the move was canceled, which could happen if the motor was disabled, if a node stop was triggered, or if another command interrupted the move. This helps us determine if the failure to reach target velocity was due to an external interruption rather than an alert condition.
    mnStatusReg result;                                 // Store results from testing the Rising register. This will allow us to determine if any of the conditions we were checking for (alerts or move cancellation) occurred during the velocity ramp-up, which helps us understand why we might not have reached the target velocity successfully.
    
    node.Status.Rise.Refresh();                         // Refresh the Rising status register to ensure we have the latest events that occurred during the move. This is important because we want to check for any alerts or cancellations that happened while we were waiting for the motor to reach the target velocity.
    
    // Verify the motor didn't go into alert during the move and that the move wasn't cancelled. If either of these conditions occurred, we want to report it and return false to indicate that we did not successfully reach the target velocity.
    if (node.Status.Rise.TestAndClear(mask, result)) {
        if (result.cpm.AlertPresent) printf("Node[%d]: Alert during velocity ramp.\n", node.Info.Ex.NodeIndex());
        return false;               // Move did not complete successfully due to an alert or cancellation
    }
    
    printf("Node[%d]: Target Velocity Reached.\n", node.Info.Ex.NodeIndex());
    return true;                    // Move was successful and target velocity was reached without any alerts or cancellations
}
