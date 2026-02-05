
        let currentStep = 0;
        let stream = null;
        let SESSION_ID = null;
        let animationFrameId = null;
        let actualFacingMode = null;
        const params = new URLSearchParams(window.location.search);
        const TENANT_SLUG = window.TENANT_SLUG || params.get("tenant") || params.get("tenant_slug");
        const CUSTOMER_ID = window.CUSTOMER_ID || params.get("customer_id");
        let capturedImages = {
            front: null,
            back: null,
            selfie: null
        };
        let capturedPaths = {
            front: null,
            back: null,
            selfie: null
        };
        let livenessCompleted = false;
        let livenessListenerAttached = false;
        let livenessCheckInterval = null;

        const steps = [
            { id: 'front', title: 'ID Card Front', icon: '📄', instruction: 'Position the FRONT of your ID card within the frame' },
            { id: 'back', title: 'ID Card Back', icon: '📄', instruction: 'Position the BACK of your ID card within the frame' },
            { id: 'liveness', title: 'Liveness Check', icon: '🎭', instruction: 'Verifying you are a real person...' },
            { id: 'selfie', title: 'Selfie Photo', icon: '🤳', instruction: 'Position your face within the frame' },
            { id: 'verify', title: 'Verification', icon: '✓', instruction: 'Verifying your identity...' }
        ];

        async function startVerification() {
              try {
                // 1) Create session first
                const res = await fetch("/session/start", {
                  method: "POST",
                  headers: { "Content-Type": "application/json" },
                  body: JSON.stringify({ tenant_slug: TENANT_SLUG, customer_id: CUSTOMER_ID }),
                });
                const data = await res.json();

                if (!data.success) {
                  showStatus("error", "Failed to start session");
                  return;
                }

                SESSION_ID = data.session_id;
                console.log("SESSION_ID:", SESSION_ID);

                // 2) Start your existing UI flow
                document.getElementById('startScreen').classList.add('hidden');
                document.getElementById('cameraContainer').classList.add('active');

                currentStep = 0;
                updateStepIndicator(0);

                await startCamera();
              } catch (err) {
                console.error(err);
                showStatus("error", "Session start failed: " + err.message);
              }
        }


        async function startCamera() {
              try {
                const stepId = steps[currentStep].id;
                const video = document.getElementById('video');

                // Stop any existing streams
                if (stream) {
                    stream.getTracks().forEach(t => t.stop());
                    stream = null;
                }
                if (animationFrameId) {
                    cancelAnimationFrame(animationFrameId);
                    animationFrameId = null;
                }

                // Clear video source
                video.srcObject = null;

                console.log(`Starting camera for step: ${stepId}`);

                const constraints = {
                  video: {
                    facingMode: stepId === 'selfie' ? 'user' : { ideal: 'environment' },
                    width: { ideal: 1280 },
                    height: { ideal: 720 }
                  }
                };

                // Request camera access
                stream = await navigator.mediaDevices.getUserMedia(constraints);

                // Set video source
                video.srcObject = stream;

                // Check which camera we actually got
                const videoTrack = stream.getVideoTracks()[0];
                const settings = videoTrack.getSettings();
                actualFacingMode = settings.facingMode;

                console.log(`Step: ${stepId}, Requested: ${stepId === 'selfie' ? 'user' : 'environment'}, Got: ${actualFacingMode}`);

                // ✅ ALWAYS mirror preview by default (natural mirror view)
                // ONLY remove mirror if we detect back/environment camera
                if (actualFacingMode === 'environment') {
                    video.classList.add('no-mirror');
                } else {
                    video.classList.remove('no-mirror');
                }

                // Wait for video to be ready
                await new Promise((resolve, reject) => {
                  const timeout = setTimeout(() => reject(new Error('Video load timeout')), 10000);

                  video.onloadedmetadata = () => {
                    clearTimeout(timeout);
                    video.play().then(() => {
                        console.log('Video playing successfully');
                        resolve();
                    }).catch(reject);
                  };
                });

                updateInstructions();
                setupCaptureButton();

              } catch (error) {
                console.error('Camera error:', error);

                // More user-friendly error messages
                let errorMessage = 'Camera access failed: ';
                if (error.name === 'NotAllowedError' || error.name === 'PermissionDeniedError') {
                    errorMessage = 'Camera permission denied. Please allow camera access in your browser settings.';
                } else if (error.name === 'NotFoundError' || error.name === 'DevicesNotFoundError') {
                    errorMessage = 'No camera found on your device.';
                } else if (error.name === 'NotReadableError' || error.name === 'TrackStartError') {
                    errorMessage = 'Camera is already in use by another application.';
                } else {
                    errorMessage += error.message;
                }

                showStatus('error', errorMessage);
                throw error; // Re-throw so calling function can handle it
              }
        }

        function setupCaptureButton() {
            const captureBtn = document.getElementById('captureBtn');
            captureBtn.onclick = capturePhoto;
        }

        function updateInstructions() {
            const step = steps[currentStep];
            document.getElementById('instructions').textContent = step.instruction;

            const guideBox = document.getElementById('guideBox');
            if (step.id === 'selfie') {
                guideBox.classList.add('selfie');
            } else {
                guideBox.classList.remove('selfie');
            }
        }

        function updateStepIndicator(step) {
            for (let i = 0; i < 5; i++) {
                const stepEl = document.getElementById(`step${i + 1}`);
                stepEl.classList.remove('active', 'completed');
                if (i < step) {
                    stepEl.classList.add('completed');
                } else if (i === step) {
                    stepEl.classList.add('active');
                }
            }
        }

        function capturePhoto() {
            const video = document.getElementById('video');
            const canvas = document.getElementById('canvas');
            const ctx = canvas.getContext('2d');
            const stepId = steps[currentStep].id;

            canvas.width = video.videoWidth;
            canvas.height = video.videoHeight;

            // ✅ For front camera (mirrored preview):
            // - Preview is mirrored (natural view)
            // - Capture should be direct (un-mirrored) so text is readable
            // For back camera: direct capture (already correct)

            // Always capture directly from video without mirroring
            // This ensures ID card text is readable in the saved image
            ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

            const imageData = canvas.toDataURL('image/jpeg', 0.95);
            capturedImages[stepId] = imageData;

            document.getElementById('cameraContainer').classList.remove('active');
            document.getElementById('previewContainer').classList.add('active');
            document.getElementById('previewImage').src = imageData;
        }

        function retakePhoto() {
            document.getElementById('previewContainer').classList.remove('active');
            document.getElementById('cameraContainer').classList.add('active');
        }

        async function confirmPhoto() {
            if (!SESSION_ID) {
              showStatus("error", "Missing session. Please restart verification.");
              return;
            }
            const stepId = steps[currentStep].id;
            const imageData = capturedImages[stepId];

            showStatus('loading', 'Uploading and checking image quality...');

            try {
            const response = await fetch('/capture/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    session_id: SESSION_ID,
                    tenant_slug: TENANT_SLUG,
                    image: imageData,
                    type: stepId
                })
            });

                const data = await response.json();

                if (!data.success) {
                    showStatus('error', data.error);
                    setTimeout(() => {
                        retakePhoto();
                    }, 2000);
                    return;
                }

                capturedPaths[stepId] = data.filename;
                showStatus('success', `${steps[currentStep].title} captured successfully!`);

                setTimeout(() => {
                    hideStatus();
                    document.getElementById('previewContainer').classList.remove('active');

                    currentStep++;

                    if (currentStep === 2) {
                        stopCamera();
                        updateStepIndicator(2);
                        document.getElementById('livenessScreen').classList.add('active');
                    } else if (currentStep < 4) {
                        updateStepIndicator(currentStep);
                        document.getElementById('cameraContainer').classList.add('active');
                        startCamera();
                    } else {
                        stopCamera();
                        verifyIdentity();
                    }
                }, 1500);

            } catch (error) {
                showStatus('error', 'Upload failed: ' + error.message);
            }
        }

        function stopCamera() {
            if (stream) {
                stream.getTracks().forEach(track => track.stop());
                stream = null;
            }
            if (animationFrameId) {
                cancelAnimationFrame(animationFrameId);
                animationFrameId = null;
            }
        }

        async function startLivenessDetection() {
          if (!SESSION_ID) {
            showStatus("error", "Missing session. Please restart verification.");
            return;
          }

          const w = window.open(
            `/liveness?session_id=${encodeURIComponent(SESSION_ID)}`,
            "livenessWindow",
            "width=520,height=820"
          );

          if (!w) {
            showStatus("error", "Popup blocked. Allow popups for this site (localhost) and try again.");
            return;
          }

          showStatus("loading", "Starting liveness detection...");

          try {
            await fetch("/start-liveness/", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ session_id: SESSION_ID, tenant_slug: TENANT_SLUG }),
            });
          } catch (e) {
            console.log("start-liveness failed:", e);
          }

          if (livenessListenerAttached) return;
          livenessListenerAttached = true;

          window.addEventListener(
            "message",
            async (event) => {
              try {
                if (!event.data || event.data.type !== "liveness_result") return;

                const result = event.data.data || {};
                result.session_id = SESSION_ID; // source of truth

                // Save to backend (pick ONE endpoint!)
                await fetch("/liveness-result", {
                  method: "POST",
                  headers: { "Content-Type": "application/json" },
                  body: JSON.stringify({ ...result, tenant_slug: TENANT_SLUG, customer_id: CUSTOMER_ID }),
                });

                if (result.verified) {
                  livenessCompleted = true;
                  showStatus("success", `✓ Liveness verified! Confidence: ${result.confidence}%`);
                  setTimeout(() => proceedAfterLiveness(), 1500);
                } else {
                  showStatus("error", "Liveness verification failed. Please try again.");
                  setTimeout(() => hideStatus(), 3000);
                }
              } catch (e) {
                console.log("Liveness handler error:", e);
                showStatus("error", "Failed to save liveness result.");
              } finally {
                livenessListenerAttached = false;
              }
            },
            { once: true }
          );
        }



        function skipLiveness() {
            if (confirm('Skipping liveness detection may reduce security. Continue anyway?')) {
                showStatus('warning', 'Liveness check skipped. Proceeding with selfie capture...');
                setTimeout(() => {
                    proceedAfterLiveness();
                }, 1500);
            }
        }

        async function proceedAfterLiveness() {
            hideStatus();
            document.getElementById('livenessScreen').classList.remove('active');
            currentStep = 3;
            updateStepIndicator(currentStep);

            // Show camera container first
            document.getElementById('cameraContainer').classList.add('active');

            // Add a small delay to ensure DOM is ready
            await new Promise(resolve => setTimeout(resolve, 100));

            // Then start camera
            try {
                await startCamera();
            } catch (error) {
                console.error('Camera start error:', error);
                showStatus('error', 'Camera permission denied. Please allow camera access and try again.');

                // Show retry button
                setTimeout(() => {
                    if (confirm('Camera access was denied. Would you like to try again?')) {
                        proceedAfterLiveness();
                    } else {
                        // Go back to liveness screen
                        document.getElementById('cameraContainer').classList.remove('active');
                        document.getElementById('livenessScreen').classList.add('active');
                        currentStep = 2;
                        updateStepIndicator(currentStep);
                    }
                }, 1000);
            }
        }

        async function verifyIdentity() {
            updateStepIndicator(4);
            showStatus('loading', 'Verifying your identity... This may take a moment.');

            try {
                const response = await fetch('/verify/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        session_id: SESSION_ID,
                        tenant_slug: TENANT_SLUG,
                        customer_id: CUSTOMER_ID,
                        front_image: capturedPaths.front,
                        back_image: capturedPaths.back,
                        selfie_image: capturedPaths.selfie,
                        liveness_verified: livenessCompleted
                    })
                });

                const data = await response.json();

                hideStatus();
                showResult(data);

            } catch (error) {
                hideStatus();
                showStatus('error', 'Verification failed: ' + error.message);
            }
        }

        function showResult(data) {
            const resultContainer = document.getElementById('verificationResult');
            const resultIcon = document.getElementById('resultIcon');
            const resultTitle = document.getElementById('resultTitle');
            const resultMessage = document.getElementById('resultMessage');
            const resultDetails = document.getElementById('resultDetails');

            if (data.success && data.verified) {
                resultIcon.textContent = '✅';
                resultIcon.className = 'result-icon success';
                resultTitle.textContent = 'Verification Successful!';
                resultMessage.textContent = `Identity confirmed with ${data.confidence.toFixed(1)}% confidence.`;
                resultDetails.innerHTML = `
                    <div style="background: #f5f5f5; padding: 15px; border-radius: 10px; margin-top: 20px; text-align: left;">
                        <strong>Verification Details:</strong><br>
                        Similarity Score: ${data.similarity.toFixed(1)}%<br>
                        Liveness: ${livenessCompleted ? '✓ Verified' : '⚠ Skipped'}<br>
                        Status: Verified ✓
                    </div>
                `;
            } else {
                resultIcon.textContent = '❌';
                resultIcon.className = 'result-icon failed';
                resultTitle.textContent = 'Verification Failed';
                resultMessage.textContent = data.error || 'Identity could not be verified. Please try again.';
                resultDetails.innerHTML = '';
            }

            resultContainer.classList.add('active');
        }

        function showStatus(type, message) {
            const statusEl = document.getElementById('statusMessage');
            statusEl.className = `status-message active ${type}`;
            statusEl.innerHTML = type === 'loading' ?
                `<div class="spinner"></div>${message}` :
                message;
        }

        function hideStatus() {
            document.getElementById('statusMessage').classList.remove('active');
        }

        function startOver() {
            location.reload();
        }

        window.addEventListener('beforeunload', () => {
            stopCamera();
            if (livenessCheckInterval) {
                clearInterval(livenessCheckInterval);
            }
        });
