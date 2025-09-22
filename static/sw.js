// Service Worker for Sistema OS PWA
// Minimal implementation for PWA registration

const CACHE_NAME = 'olivium-v1-modern';

// Install event - basic PWA registration
self.addEventListener('install', function(event) {
  console.log('Service Worker: Installing...');
  self.skipWaiting();
});

// Activate event
self.addEventListener('activate', function(event) {
  console.log('Service Worker: Activating...');
  event.waitUntil(self.clients.claim());
});

// Fetch event - pass through all requests to network
// No caching for now to maintain all existing functionality
self.addEventListener('fetch', function(event) {
  // Simply pass through all requests to the network
  // This ensures all existing functionality works exactly as before
  event.respondWith(fetch(event.request));
});