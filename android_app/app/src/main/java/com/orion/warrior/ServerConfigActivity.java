package com.orion.warrior;

import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.TextView;
import android.widget.Toast;

import androidx.appcompat.app.AppCompatActivity;
import androidx.core.content.ContextCompat;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class ServerConfigActivity extends AppCompatActivity {

    public static final String PREFS_NAME = "OrionPrefs";
    public static final String KEY_SERVER_URL = "server_url";
    public static final String DEFAULT_URL = "http://100.116.4.49:8000";

    private EditText etServerUrl;
    private TextView tvStatus;
    private Button btnTest;
    private Button btnSave;
    private final ExecutorService executor = Executors.newSingleThreadExecutor();
    private final Handler mainHandler = new Handler(Looper.getMainLooper());

    public static String getServerUrl(Context context) {
        SharedPreferences prefs = context.getSharedPreferences(PREFS_NAME, MODE_PRIVATE);
        return prefs.getString(KEY_SERVER_URL, DEFAULT_URL);
    }

    public static void setServerUrl(Context context, String url) {
        SharedPreferences prefs = context.getSharedPreferences(PREFS_NAME, MODE_PRIVATE);
        prefs.edit().putString(KEY_SERVER_URL, url).apply();
    }

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_server_config);

        etServerUrl = findViewById(R.id.etServerUrl);
        tvStatus = findViewById(R.id.tvStatus);
        btnTest = findViewById(R.id.btnTest);
        btnSave = findViewById(R.id.btnSave);

        String currentUrl = getServerUrl(this);
        etServerUrl.setText(currentUrl);

        btnTest.setOnClickListener(v -> testConnection());
        btnSave.setOnClickListener(v -> saveAndConnect());
    }

    private String getNormalizedUrl() {
        String input = etServerUrl.getText().toString().trim();
        if (input.isEmpty()) {
            input = DEFAULT_URL;
        }
        if (!input.startsWith("http://") && !input.startsWith("https://")) {
            input = "http://" + input;
        }
        if (input.endsWith("/")) {
            input = input.substring(0, input.length() - 1);
        }
        return input;
    }

    private void testConnection() {
        final String serverUrl = getNormalizedUrl();
        tvStatus.setText("Connecting to " + serverUrl + "...");
        tvStatus.setTextColor(ContextCompat.getColor(this, R.color.text_muted));
        btnTest.setEnabled(false);

        executor.execute(() -> {
            boolean success = false;
            String message = "";
            try {
                URL url = new URL(serverUrl + "/api/health");
                HttpURLConnection conn = (HttpURLConnection) url.openConnection();
                conn.setRequestMethod("GET");
                conn.setConnectTimeout(4000);
                conn.setReadTimeout(4000);

                int code = conn.getResponseCode();
                if (code == 200) {
                    BufferedReader in = new BufferedReader(new InputStreamReader(conn.getInputStream()));
                    StringBuilder sb = new StringBuilder();
                    String line;
                    while ((line = in.readLine()) != null) {
                        sb.append(line);
                    }
                    in.close();
                    success = true;
                    message = "Connected! Orion Server is online.";
                } else {
                    message = "Server returned HTTP code " + code;
                }
                conn.disconnect();
            } catch (Exception e) {
                message = "Could not reach server: " + e.getMessage();
            }

            final boolean isSuccess = success;
            final String finalMsg = message;

            mainHandler.post(() -> {
                btnTest.setEnabled(true);
                tvStatus.setText(finalMsg);
                tvStatus.setTextColor(ContextCompat.getColor(
                        ServerConfigActivity.this,
                        isSuccess ? R.color.status_green : R.color.status_red
                ));
            });
        });
    }

    private void saveAndConnect() {
        String finalUrl = getNormalizedUrl();
        setServerUrl(this, finalUrl);
        Toast.makeText(this, "Orion server set: " + finalUrl, Toast.LENGTH_SHORT).show();
        setResult(RESULT_OK);
        finish();
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        executor.shutdown();
    }
}

