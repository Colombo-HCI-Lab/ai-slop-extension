const http = require('http');
const url = require('url');

const port = process.argv[2] || 8080;
let authCode = null;

const server = http.createServer((req, res) => {
    const parsedUrl = url.parse(req.url, true);
    
    if (parsedUrl.pathname === '/') {
        const code = parsedUrl.query.code;
        const error = parsedUrl.query.error;
        
        if (code) {
            authCode = code;
            res.writeHead(200, { 'Content-Type': 'text/html' });
            res.end(`
                <html>
                    <head><title>Authentication Successful</title></head>
                    <body style="font-family: Arial, sans-serif; text-align: center; padding: 50px;">
                        <h2 style="color: green;">✓ Authentication Successful!</h2>
                        <p>Authorization code received. You can close this window.</p>
                        <p>The upload script will continue automatically...</p>
                    </body>
                </html>
            `);
            setTimeout(() => {
                console.log(code);
                server.close();
                process.exit(0);
            }, 2000);
        } else if (error) {
            res.writeHead(400, { 'Content-Type': 'text/html' });
            res.end(`
                <html>
                    <head><title>Authentication Error</title></head>
                    <body style="font-family: Arial, sans-serif; text-align: center; padding: 50px;">
                        <h2 style="color: red;">✗ Authentication Failed</h2>
                        <p>Error: ${error}</p>
                        <p>Please try again or check your OAuth configuration.</p>
                    </body>
                </html>
            `);
            setTimeout(() => {
                console.error(`OAuth Error: ${error}`);
                server.close();
                process.exit(1);
            }, 2000);
        } else {
            res.writeHead(404, { 'Content-Type': 'text/plain' });
            res.end('Not found');
        }
    } else {
        res.writeHead(404, { 'Content-Type': 'text/plain' });
        res.end('Not found');
    }
});

server.listen(port, () => {
    console.log(`OAuth callback server listening on port ${port}`);
});

// Timeout after 5 minutes
setTimeout(() => {
    console.error('OAuth timeout - no response received within 5 minutes');
    server.close();
    process.exit(1);
}, 300000);