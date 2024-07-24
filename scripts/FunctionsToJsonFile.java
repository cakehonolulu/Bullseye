// Import Ghidra classes
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.FunctionIterator;
import ghidra.program.model.address.Address;
import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import java.io.BufferedWriter;
import java.io.FileWriter;
import java.io.IOException;

public class FunctionsToJsonFile extends GhidraScript {

    @Override
    protected void run() throws Exception {
        // Define the output file path
        String outputFilePath = askFile("Select output file", "Save").getAbsolutePath();
        
        // Create a JSON array for replacements
        JsonArray replacementsArray = new JsonArray();
        
        // Get the function manager
        var functionManager = currentProgram.getFunctionManager();
        
        // Iterate over all functions
        FunctionIterator functions = functionManager.getFunctions(true);
        while (functions.hasNext()) {
            Function function = functions.next();
            // Get function name, size, and start address
            String name = function.getName();
            long size = function.getBody().getNumAddresses();  // Function size
            Address startAddress = function.getEntryPoint();    // Function start address
            
            // Convert function names starting with "FUN_" to uppercase
            if (name.startsWith("FUN_")) {
                name = name.toUpperCase();
            }
            
            // Subtract 0xFF000 from the address
            long originalAddress = startAddress.getOffset();
            long adjustedAddress = originalAddress - 0xFF000;
            
            // Format the adjusted address as a hexadecimal string
            String hexAddress = "0x" + Long.toHexString(adjustedAddress).toUpperCase();
            
            // Create JSON object for the current function
            JsonObject functionObject = new JsonObject();
            functionObject.addProperty("file_path", name + ".bin");
            functionObject.addProperty("offset", hexAddress);
            functionObject.addProperty("expected_size", size);
            
            // Add to JSON array
            replacementsArray.add(functionObject);
        }
        
        // Create JSON object with replacements array
        JsonObject rootObject = new JsonObject();
        rootObject.add("replacements", replacementsArray);
        
        // Create Gson instance with pretty-printing enabled
        Gson gson = new GsonBuilder().setPrettyPrinting().create();
        
        // Write JSON to file
        try (BufferedWriter writer = new BufferedWriter(new FileWriter(outputFilePath))) {
            gson.toJson(rootObject, writer);  // Write formatted JSON
        } catch (IOException e) {
            println("Error writing to file: " + e.getMessage());
        }
        
        // Notify user
        println("Function details written to " + outputFilePath);
    }
}
